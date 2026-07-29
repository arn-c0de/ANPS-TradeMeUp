"""Billed-token accounting on the LLM service.

Providers report exactly what they charged for; the service used to discard
those numbers, leaving a characters/4 estimate as the only signal. These tests
cover the counters that replaced it.
"""
import types

import pytest

from src.services.llm_service import LLMService, TokenUsage


class TestTokenUsage:
    def test_starts_empty(self):
        usage = TokenUsage()
        assert usage.total_tokens == 0
        assert usage.calls == 0

    def test_accumulates(self):
        usage = TokenUsage()
        usage.add(100, 20)
        usage.add(50, 5)

        assert usage.prompt_tokens == 150
        assert usage.completion_tokens == 25
        assert usage.total_tokens == 175
        assert usage.calls == 2

    def test_tolerates_missing_counts(self):
        """A provider that omits usage must not crash the pipeline."""
        usage = TokenUsage()
        usage.add(None, None)

        assert usage.total_tokens == 0
        assert usage.calls == 1

    def test_as_dict_includes_total(self):
        usage = TokenUsage()
        usage.add(10, 3)
        assert usage.as_dict() == {
            'prompt_tokens': 10,
            'completion_tokens': 3,
            'calls': 1,
            'total_tokens': 13,
        }


def _openai_service(responses):
    """An LLMService wired to a fake OpenAI client returning ``responses``."""
    service = object.__new__(LLMService)
    service.provider = "openai"
    service.model = "gpt-4o-mini"
    service.temperature = 0.1
    service.max_tokens = 4096
    service.usage = TokenUsage()
    service.last_usage = None

    from threading import Lock
    service._usage_lock = Lock()

    calls = iter(responses)

    class _Completions:
        def create(self, **kwargs):
            return next(calls)

    service.openai_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_Completions())
    )
    return service


def _openai_response(text, prompt_tokens, completion_tokens):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text))],
        usage=types.SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )


class TestOpenAIUsageCapture:
    def test_records_reported_tokens(self):
        service = _openai_service([_openai_response("hello", 123, 45)])

        service._generate_openai("prompt", None, 0.1, 4096)

        assert service.last_usage['prompt_tokens'] == 123
        assert service.last_usage['completion_tokens'] == 45
        assert service.last_usage['total_tokens'] == 168
        assert service.last_usage['model'] == "gpt-4o-mini"
        assert service.get_usage()['calls'] == 1

    def test_accumulates_across_calls(self):
        service = _openai_service([
            _openai_response("a", 100, 10),
            _openai_response("b", 200, 20),
        ])

        service._generate_openai("one", None, 0.1, 4096)
        service._generate_openai("two", None, 0.1, 4096)

        usage = service.get_usage()
        assert usage['prompt_tokens'] == 300
        assert usage['completion_tokens'] == 30
        assert usage['total_tokens'] == 330
        assert usage['calls'] == 2

    def test_missing_usage_block_is_not_fatal(self):
        response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="x"))],
            usage=None,
        )
        service = _openai_service([response])

        assert service._generate_openai("p", None, 0.1, 4096) == "x"
        assert service.get_usage()['total_tokens'] == 0
        assert service.get_usage()['calls'] == 1

    def test_reset_returns_and_clears(self):
        service = _openai_service([_openai_response("a", 10, 2)])
        service._generate_openai("one", None, 0.1, 4096)

        previous = service.reset_usage()

        assert previous['total_tokens'] == 12
        assert service.get_usage()['total_tokens'] == 0
        assert service.get_usage()['calls'] == 0
        assert service.last_usage is None


class TestLazyConstruction:
    def test_service_is_not_built_at_import(self):
        """Importing the module must not construct a client or probe a server."""
        import src.services.llm_service as module

        # Reach past the proxy: the private singleton is the real object.
        module._llm_service = None
        assert module._llm_service is None

        # Touching an attribute is what builds it.
        module.get_llm_service()
        assert isinstance(module._llm_service, LLMService)

    def test_proxy_forwards_to_the_singleton(self):
        import src.services.llm_service as module

        module._llm_service = None
        service = module.get_llm_service()

        assert module.llm_service.provider == service.provider
        assert module.llm_service.get_usage() == service.get_usage()


@pytest.mark.parametrize(
    "prompt_eval_count,eval_count,expected",
    [(80, 12, 92), (0, 0, 0), (None, None, 0)],
)
def test_ollama_usage_capture(monkeypatch, prompt_eval_count, eval_count, expected):
    service = object.__new__(LLMService)
    service.provider = "ollama"
    service.model = "llama2"
    service.ollama_base_url = "http://localhost:11434"
    service.usage = TokenUsage()
    service.last_usage = None

    from threading import Lock
    service._usage_lock = Lock()

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": "text",
                "prompt_eval_count": prompt_eval_count,
                "eval_count": eval_count,
            }

    monkeypatch.setattr(
        "src.services.llm_service.requests.post", lambda *a, **k: _Response()
    )

    assert service._generate_ollama("p", None, 0.1, 100) == "text"
    assert service.get_usage()['total_tokens'] == expected
