from unittest.mock import Mock

from src.agents.ingestion_agent import IngestionAgent


def test_fetch_news_api_skips_placeholder_key_without_request():
    agent = IngestionAgent(db=Mock())
    agent.session.get = Mock()

    saved = agent.fetch_news_api("your_news_api_key_here")

    assert saved == 0
    agent.session.get.assert_not_called()
