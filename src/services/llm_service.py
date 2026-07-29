"""LLM Service - Unified interface for Ollama, OpenAI, and Anthropic."""
import json
import logging
import re
from threading import Lock
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.utils.redact import redact_url

# Without a timeout a hung Ollama server blocks the pipeline forever, and the
# @retry wrapper never fires because the call simply never returns.
OLLAMA_PROBE_TIMEOUT = 10        # seconds, connection test only
OLLAMA_GENERATE_TIMEOUT = 300    # seconds, local generation can be slow

logger = logging.getLogger(__name__)
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

# Rough characters-per-token ratio used for prompt budgeting.
CHARS_PER_TOKEN = 4

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_MODEL = "all-mpnet-base-v2"
LOCAL_EMBEDDING_DEVICE = "cpu"  # CPU only, to avoid GPU memory overflow

_local_embedding_model = None
_local_embedding_lock = Lock()


def _get_local_embedding_model():
    """Load the local sentence-transformer once and reuse it.

    Constructing SentenceTransformer reads a few hundred MB from disk, so
    building it per call turned every embedding into a model load.
    """
    global _local_embedding_model

    if _local_embedding_model is None:
        with _local_embedding_lock:
            if _local_embedding_model is None:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Loading SentenceTransformer %s on %s",
                    LOCAL_EMBEDDING_MODEL,
                    LOCAL_EMBEDDING_DEVICE,
                )
                _local_embedding_model = SentenceTransformer(
                    LOCAL_EMBEDDING_MODEL
                ).to(LOCAL_EMBEDDING_DEVICE)

    return _local_embedding_model


def normalize_openai_base_url(base_url: str | None) -> str:
    """Return a safe OpenAI base URL, falling back to the official endpoint."""
    if not base_url:
        return DEFAULT_OPENAI_BASE_URL

    normalized = base_url.strip()
    if not normalized:
        return DEFAULT_OPENAI_BASE_URL

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        logger.warning(
            "Ignoring invalid OPENAI_BASE_URL without http(s) scheme: %s",
            normalized,
        )
        return DEFAULT_OPENAI_BASE_URL

    return normalized


class LLMService:
    """
    Unified LLM service supporting multiple providers:
    - Ollama (local)
    - OpenAI (GPT-3.5/GPT-4)
    - Anthropic (Claude)
    """

    def __init__(self, provider: str | None = None):
        """
        Initialize LLM service.

        Args:
            provider: LLM provider ("ollama", "openai", "anthropic").
                     If None, uses settings.llm_provider
        """
        self.provider = provider or settings.llm_provider
        self.temperature = settings.default_temperature
        self.max_tokens = settings.max_tokens

        logger.info(f"Initialized LLM service with provider: {self.provider}")

        # Initialize provider-specific clients
        if self.provider == "openai":
            try:
                import os

                import httpx
                from openai import OpenAI

                openai_base_url = normalize_openai_base_url(settings.openai_base_url)

                # Configure OpenAI client with timeout and proxy support
                client_kwargs = {
                    "api_key": settings.openai_api_key,
                    "base_url": openai_base_url,
                    "timeout": 60.0,  # 60 second timeout
                }

                if openai_base_url != DEFAULT_OPENAI_BASE_URL:
                    logger.info(f"Using custom OpenAI base URL: {redact_url(openai_base_url)}")
                else:
                    logger.info("Using default OpenAI base URL")

                # Check proxy configuration
                http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
                https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

                # Detect invalid proxy configurations (e.g., discard port 9)
                invalid_proxy_ports = [9]  # Port 9 is discard port
                use_proxy = True

                if http_proxy or https_proxy:
                    # Check if proxy points to invalid port
                    for proxy_url in [http_proxy, https_proxy]:
                        if proxy_url:
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(proxy_url)
                                if parsed.port in invalid_proxy_ports:
                                    logger.warning(f"Invalid proxy configuration detected: {proxy_url} (port {parsed.port} is discard port)")
                                    logger.warning("Disabling proxy usage. Set correct proxy or unset HTTP_PROXY/HTTPS_PROXY if no proxy needed.")
                                    use_proxy = False
                                    break
                            except Exception:
                                pass

                    if use_proxy:
                        logger.info(f"Proxy detected: HTTP_PROXY={http_proxy}, HTTPS_PROXY={https_proxy}")

                # Configure httpx client - disable proxy if invalid, otherwise trust_env
                if use_proxy:
                    client_kwargs["http_client"] = httpx.Client(timeout=60.0, trust_env=True)
                else:
                    # Explicitly disable proxy by setting trust_env=False
                    client_kwargs["http_client"] = httpx.Client(timeout=60.0, trust_env=False)
                    logger.info("Proxy disabled due to invalid configuration")

                self.openai_client = OpenAI(**client_kwargs)
                self.model = settings.openai_model
                logger.info(f"OpenAI client initialized with model: {self.model}")
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise

        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic
                self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
                self.model = settings.anthropic_model
            except ImportError:
                logger.error("Anthropic library not installed. Run: pip install anthropic")
                raise

        elif self.provider == "ollama":
            self.ollama_base_url = settings.ollama_base_url
            self.model = settings.ollama_model
            # Test connection
            self._test_ollama_connection()

        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _test_ollama_connection(self):
        """Test connection to Ollama server."""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=OLLAMA_PROBE_TIMEOUT)
            if response.status_code == 200:
                models = response.json().get("models", [])
                logger.info(f"Connected to Ollama. Available models: {[m['name'] for m in models]}")
            else:
                logger.warning("Ollama server responded but may not be fully ready")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama (host: {redact_url(self.ollama_base_url)}): {e}")
            logger.error("Make sure Ollama is running: ollama serve")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """
        Generate text using the configured LLM provider.

        Args:
            prompt: User prompt
            system_prompt: System prompt (instructions)
            temperature: Sampling temperature (overrides default)
            max_tokens: Max tokens to generate (overrides default)
            json_mode: Ask the provider to constrain output to valid JSON.
                Supported natively by OpenAI and Ollama; ignored elsewhere.

        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            if self.provider == "ollama":
                return self._generate_ollama(prompt, system_prompt, temp, tokens, json_mode)
            elif self.provider == "openai":
                return self._generate_openai(prompt, system_prompt, temp, tokens, json_mode)
            elif self.provider == "anthropic":
                return self._generate_anthropic(prompt, system_prompt, temp, tokens)
            # Falling through returned None, which callers then tried to parse.
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Error generating text with {self.provider}: {e}")
            raise

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        """Generate text using Ollama."""
        url = f"{self.ollama_base_url}/api/generate"

        # Build the full prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "temperature": temperature,
            "stream": False,
            "options": {
                "num_predict": max_tokens
            }
        }
        if json_mode:
            # Constrains decoding to valid JSON, which removes the need to
            # repair the response with regular expressions afterwards.
            payload["format"] = "json"

        response = requests.post(url, json=payload, timeout=OLLAMA_GENERATE_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        """Generate text using OpenAI."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        request_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            # Guarantees syntactically valid JSON, so a malformed reply can no
            # longer waste a whole call.
            request_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.openai_client.chat.completions.create(**request_kwargs)

            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI API error: {error_msg}")

            # Provide helpful error messages
            if "Connection error" in error_msg or "10061" in error_msg:
                logger.error("Connection to OpenAI API failed. Possible causes:")
                logger.error("  1. Proxy/Network issue - check HTTP_PROXY/HTTPS_PROXY environment variables")
                logger.error("  2. Firewall blocking connection")
                logger.error("  3. OpenAI API endpoint unreachable")
                logger.error("  4. Check OPENAI_BASE_URL in .env.local if using custom endpoint")

            raise

    def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using Anthropic Claude."""
        message = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None
    ) -> dict:
        """
        Generate JSON output from LLM.

        Args:
            prompt: User prompt (should request JSON output)
            system_prompt: System prompt
            temperature: Sampling temperature

        Returns:
            Parsed JSON as dictionary
        """
        json_mode = self.supports_json_mode()

        # Only append the instruction when the provider cannot enforce JSON
        # itself and the prompt does not already ask for it. The templates in
        # config/prompts already end with such a line, so appending
        # unconditionally sent the same instruction twice.
        json_prompt = prompt
        if not json_mode and not self._asks_for_json(prompt):
            json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON, no additional text."

        response = self.generate(
            json_prompt, system_prompt, temperature, json_mode=json_mode
        )

        parsed = self._parse_json_response(response)
        if parsed is not None:
            return parsed

        logger.error(f"Failed to parse JSON from response: {response[:500]}")
        raise ValueError("Could not parse valid JSON from LLM response")

    def supports_json_mode(self) -> bool:
        """Whether the active provider can constrain output to valid JSON."""
        return self.provider in {"openai", "ollama"}

    @staticmethod
    def _asks_for_json(prompt: str) -> bool:
        """Rough check for a prompt that already demands JSON-only output."""
        tail = prompt[-400:].lower()
        return "json" in tail and ("only" in tail or "no additional text" in tail)

    @staticmethod
    def _parse_json_response(response: str) -> dict | None:
        """Parse an LLM reply into a dict, repairing common damage.

        Returns None when nothing usable could be recovered.
        """
        if not response:
            return None

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}. Attempting extraction...")

        # JSON wrapped in a markdown code fence
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        # Any brace-delimited object, with common damage repaired
        candidate = re.search(r'\{.*\}', response, re.DOTALL)
        if candidate:
            json_str = candidate.group(0)
            # Trailing commas before a closing brace/bracket
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            # Missing comma between two quoted properties on separate lines
            json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        return None

    def get_embedding(self, text: str) -> list[float]:
        """
        Get text embedding using configured provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        return self.get_embedding_with_model(text)[0]

    def get_embedding_with_model(self, text: str) -> tuple[list[float], str]:
        """Embed ``text`` and report which model produced the vector.

        The two available models live in different vector spaces
        (text-embedding-3-small is 1536-dimensional, all-mpnet-base-v2 is
        768). Mixing them in one column makes similarity comparisons
        meaningless, so the model name travels with the vector and callers
        should persist it alongside.

        Returns:
            (embedding vector, model name)
        """
        # Use OpenAI embeddings if available
        if self.provider == "openai" and hasattr(self, 'openai_client'):
            try:
                response = self.openai_client.embeddings.create(
                    model=OPENAI_EMBEDDING_MODEL,
                    input=text[:8191]  # OpenAI has max input length
                )
                return response.data[0].embedding, OPENAI_EMBEDDING_MODEL
            except Exception as e:
                logger.warning(
                    "Failed to get embedding from OpenAI (%s). Falling back to %s, "
                    "which is a DIFFERENT vector space - these embeddings are not "
                    "comparable with previously stored OpenAI ones.",
                    e,
                    LOCAL_EMBEDDING_MODEL,
                )

        # Fallback: use sentence-transformers on CPU
        try:
            model = _get_local_embedding_model()
            embedding = model.encode(text, convert_to_numpy=True, device=LOCAL_EMBEDDING_DEVICE)
            return embedding.tolist(), LOCAL_EMBEDDING_MODEL
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation).

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Rough approximation: ~4 characters per token
        return len(text) // CHARS_PER_TOKEN


def truncate_for_prompt(text: str, max_tokens: int) -> str:
    """Trim ``text`` to roughly ``max_tokens`` tokens, on a word boundary.

    Callers used to slice by a hard-coded character count, which cut mid-word
    and gave no indication of the actual budget being spent.
    """
    if not text:
        return ""

    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text

    clipped = text[:max_chars]
    # Prefer the last sentence end, then the last space, so the model is not
    # handed a fragment of a word.
    for boundary in ('. ', '\n', ' '):
        cut = clipped.rfind(boundary)
        if cut > max_chars * 0.6:
            return clipped[:cut + len(boundary)].rstrip()
    return clipped


# Global LLM service instance
llm_service = LLMService()
