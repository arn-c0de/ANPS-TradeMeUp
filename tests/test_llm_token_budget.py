"""Guards on how much text the pipeline sends to the LLM.

Prompt size is the pipeline's dominant token cost, so the truncation helpers
and the "is this call worth making at all" checks are worth pinning down.
"""
import types

import pytest

from src.services.llm_service import CHARS_PER_TOKEN, truncate_for_prompt


class TestTruncateForPrompt:
    def test_short_text_is_untouched(self):
        assert truncate_for_prompt("a short article", 100) == "a short article"

    def test_empty_input(self):
        assert truncate_for_prompt("", 100) == ""
        assert truncate_for_prompt(None, 100) == ""

    def test_respects_the_budget(self):
        text = "word " * 5000
        result = truncate_for_prompt(text, 100)
        assert len(result) <= 100 * CHARS_PER_TOKEN

    def test_does_not_cut_mid_word(self):
        text = "Alpha bravo charlie delta echo foxtrot " * 200
        result = truncate_for_prompt(text, 50)
        # Whatever the cut point, the tail must be a complete token.
        assert result == result.rstrip()
        assert not result.endswith(("Alph", "brav", "charli", "delt", "fox"))

    def test_prefers_a_sentence_boundary(self):
        body = "This is a sentence. " * 100
        result = truncate_for_prompt(body, 50)
        assert result.endswith(".")


class TestEntityExtractionBudget:
    """The extraction prompt used to be a raw 3000-character slice."""

    def test_content_is_token_budgeted(self, monkeypatch):
        from src.agents import entity_mapping_agent as module

        captured = {}

        class _FakeLLM:
            provider = "openai"
            model = "gpt-4o-mini"

            def generate_json(self, prompt, **kwargs):
                captured['prompt'] = prompt
                return {'entities': []}

        agent = object.__new__(module.EntityMappingAgent)
        agent.llm = _FakeLLM()
        agent.prompt_template = "Title: {title}\nContent: {content}"

        long_body = "Acme Corporation reported strong results. " * 2000
        article = types.SimpleNamespace(
            news_id="n1", title="Acme beats", full_text=long_body
        )

        class _FakeQuery:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        db = types.SimpleNamespace(query=lambda *a, **k: _FakeQuery())

        agent._extract_entities(db, article)

        budget_chars = module.EXTRACTION_CONTENT_TOKENS * CHARS_PER_TOKEN
        # Prompt carries the template plus at most the budgeted content.
        assert len(captured['prompt']) < budget_chars + 500
        assert "Acme Corporation" in captured['prompt']


class TestFactVerificationSkipsEmptyArticles:
    def _agent(self):
        from src.agents.fact_verification_agent import FactVerificationAgent

        agent = object.__new__(FactVerificationAgent)

        class _ExplodingLLM:
            def generate_json(self, *a, **k):
                raise AssertionError("no LLM call should be made for an empty article")

        agent.llm = _ExplodingLLM()
        return agent

    def _db_returning(self, article):
        class _FakeQuery:
            def options(self, *a, **k):
                return self

            def filter(self, *a, **k):
                return self

            def first(self):
                return article

        return types.SimpleNamespace(query=lambda *a, **k: _FakeQuery())

    @pytest.mark.parametrize("key_facts", [None, [], "not-a-list"])
    def test_no_claims_means_no_llm_call(self, key_facts):
        article = types.SimpleNamespace(
            news_id="n1",
            key_facts=key_facts,
            event_type="other",
            sentiment={},
            news=types.SimpleNamespace(title="Some headline"),
        )
        agent = self._agent()

        verification = agent._verify_article_no_commit(self._db_returning(article), "n1")

        assert verification.verification_method == 'no_claims'
        assert verification.claims_verified == []
        assert verification.contradictions_found is False
        assert verification.credibility_score == agent.NO_CLAIMS_CREDIBILITY

    def test_articles_with_claims_still_reach_the_llm(self):
        from src.agents.fact_verification_agent import FactVerificationAgent

        agent = object.__new__(FactVerificationAgent)
        calls = []

        class _FakeLLM:
            def generate_json(self, prompt, **kwargs):
                calls.append(prompt)
                return {
                    'claims_verified': [{'claim': 'Revenue rose 10%', 'verdict': 'verified'}],
                    'contradictions': [],
                    'overall_credibility': 0.9,
                    'notes': 'ok',
                }

        agent.llm = _FakeLLM()

        article = types.SimpleNamespace(
            news_id="n2",
            key_facts=[{'fact': 'Revenue rose 10%', 'confidence': 0.9}],
            event_type="earnings",
            sentiment={'overall': 0.4},
            news=types.SimpleNamespace(title="Acme earnings"),
        )

        verification = agent._verify_article_no_commit(self._db_returning(article), "n2")

        assert len(calls) == 1
        assert "Revenue rose 10%" in calls[0]
        assert verification.verification_method == 'llm_cross_check'
        assert verification.credibility_score == 0.9

    def test_prompt_has_no_stray_quote_after_the_title(self):
        from src.agents.fact_verification_agent import FactVerificationAgent

        agent = object.__new__(FactVerificationAgent)
        article = types.SimpleNamespace(
            key_facts=[{'fact': 'A claim'}],
            event_type="other",
            sentiment={},
            news=types.SimpleNamespace(title="Acme beats estimates"),
        )

        prompt = agent._build_verification_prompt(article)

        assert "Article Title: Acme beats estimates\n" in prompt
        assert 'Acme beats estimates"' not in prompt
