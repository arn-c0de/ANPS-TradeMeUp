"""LLM Service - Unified interface for Ollama, OpenAI, and Anthropic."""
import json
import logging
from typing import Dict, List, Optional
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
        max_tokens: int | None = None
    ) -> str:
        """
        Generate text using the configured LLM provider.

        Args:
            prompt: User prompt
            system_prompt: System prompt (instructions)
            temperature: Sampling temperature (overrides default)
            max_tokens: Max tokens to generate (overrides default)

        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            if self.provider == "ollama":
                return self._generate_ollama(prompt, system_prompt, temp, tokens)
            elif self.provider == "openai":
                return self._generate_openai(prompt, system_prompt, temp, tokens)
            elif self.provider == "anthropic":
                return self._generate_anthropic(prompt, system_prompt, temp, tokens)
        except Exception as e:
            logger.error(f"Error generating text with {self.provider}: {e}")
            raise

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int
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

        response = requests.post(url, json=payload, timeout=OLLAMA_GENERATE_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using OpenAI."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

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
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON, no additional text."

        response = self.generate(json_prompt, system_prompt, temperature)

        # Try to extract and fix JSON from response
        try:
            # Try direct parsing
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}. Attempting extraction...")

            # Try to find JSON in code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # Try to find any JSON object
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)

                # Try to fix common JSON issues
                try:
                    # Remove trailing commas before closing braces/brackets
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    # Fix missing commas between properties (basic heuristic)
                    json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to parse JSON from response: {response[:500]}")
            raise ValueError("Could not parse valid JSON from LLM response")

    def get_embedding(self, text: str) -> list[float]:
        """
        Get text embedding using configured provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Use OpenAI embeddings if available
        if self.provider == "openai" and hasattr(self, 'openai_client'):
            try:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text[:8191]  # OpenAI has max input length
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(f"Failed to get embedding from OpenAI: {e}. Falling back to CPU embeddings.")

        # Fallback: use sentence-transformers on CPU
        try:
            import torch
            from sentence_transformers import SentenceTransformer

            # Force CPU to avoid GPU memory overflow
            device = "cpu"
            logger.info(f"Loading SentenceTransformer on {device} device")

            model = SentenceTransformer('all-mpnet-base-v2')
            model = model.to(device)
            embedding = model.encode(text, convert_to_numpy=True, device=device)
            return embedding.tolist()
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
        return len(text) // 4


# Global LLM service instance
llm_service = LLMService()
