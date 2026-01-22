"""LLM Service - Unified interface for Ollama, OpenAI, and Anthropic."""
import logging
from typing import Optional, Dict, List
import json
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM service supporting multiple providers:
    - Ollama (local)
    - OpenAI (GPT-3.5/GPT-4)
    - Anthropic (Claude)
    """

    def __init__(self, provider: Optional[str] = None):
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
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=settings.openai_api_key)
                self.model = settings.openai_model
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
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
            response = requests.get(f"{self.ollama_base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                logger.info(f"Connected to Ollama. Available models: {[m['name'] for m in models]}")
            else:
                logger.warning("Ollama server responded but may not be fully ready")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama at {self.ollama_base_url}: {e}")
            logger.error("Make sure Ollama is running: ollama serve")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
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
        system_prompt: Optional[str],
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

        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using OpenAI."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
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
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Dict:
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

        # Try to extract JSON from response
        try:
            # Try direct parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON in code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # Try to find any JSON object
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))

            logger.error(f"Failed to parse JSON from response: {response}")
            raise ValueError("Could not parse valid JSON from LLM response")

    def get_embedding(self, text: str) -> List[float]:
        """
        Get text embedding (currently using sentence-transformers as fallback).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # For now, use sentence-transformers for all providers
        # This gives consistent embeddings regardless of LLM provider
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-mpnet-base-v2')
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
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
