"""
Debug Entity Extraction - Show RAW LLM Response
"""

import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models.database import get_scoped_session
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.services.llm_service import LLMService
from src.config.settings import settings

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable httpx debug logs (too verbose)
logging.getLogger("httpx").setLevel(logging.WARNING)


def load_prompt():
    """Load entity extraction prompt"""
    prompt_path = Path(__file__).parent / "config" / "prompts" / "entity_extraction.txt"
    
    if prompt_path.exists():
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Fallback
    return """Extract companies, people, and locations mentioned in this news article.

Article:
Title: {title}
Content: {content}

Return a JSON object with this structure:
{{
  "entities": [
    {{"type": "company", "name": "Apple Inc.", "ticker": "AAPL", "relevance": 0.95}},
    {{"type": "person", "name": "Tim Cook", "role": "CEO"}},
    {{"type": "location", "name": "Cupertino, CA"}}
  ]
}}

IMPORTANT:
- Only extract entities EXPLICITLY mentioned
- For companies, try to identify ticker symbols
- Rate relevance 0-1 (how important to the story)
- Return empty array if no entities found
"""


def debug_single_article():
    """Debug entity extraction for one article"""
    
    with get_scoped_session() as db:
        # Get article WITHOUT entity mapping
        article = db.query(RawNews).outerjoin(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).filter(
            ProcessedNews.news_id.isnot(None)  # Has processed version
        ).order_by(RawNews.published_at.desc()).first()
        
        if not article:
            print("❌ No articles found!")
            return
        
        # Get processed version
        processed = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == article.news_id
        ).first()
        
        print("="*70)
        print("📰 ARTICLE DEBUG")
        print("="*70)
        print(f"Title: {article.title}")
        print(f"Source: {article.source}")
        print(f"Published: {article.published_at}")
        print()
        
        # Build content
        if processed and processed.key_facts:
            facts_text = "\n".join([
                f.get('fact', '') if isinstance(f, dict) else str(f)
                for f in processed.key_facts[:10]
            ])
            content = f"{article.title}\n\n{facts_text}"
            print("📋 Using Key Facts:")
            print(facts_text[:500])
        else:
            content = f"{article.title}\n\n{article.full_text}"
            print("📄 Using Full Text:")
            print(article.full_text[:500])
        
        print()
        print("="*70)
        print("🤖 LLM EXTRACTION")
        print("="*70)
        
        # Load prompt
        prompt_template = load_prompt()
        prompt = prompt_template.format(
            title=article.title,
            content=content[:3000]
        )
        
        print(f"Prompt length: {len(prompt)} chars")
        print()
        print("📝 PROMPT:")
        print("-"*70)
        print(prompt)
        print("-"*70)
        print()
        
        # Call LLM
        llm = LLMService()
        
        print("🔄 Calling OpenAI API...")
        try:
            result = llm.generate_json(prompt, temperature=0.1)
            
            print("✅ LLM Response:")
            print("-"*70)
            import json
            print(json.dumps(result, indent=2))
            print("-"*70)
            print()
            
            if isinstance(result, dict) and 'entities' in result:
                entities = result['entities']
                print(f"📊 Found {len(entities)} entities:")
                for ent in entities:
                    print(f"  - {ent}")
            else:
                print("⚠️ No 'entities' field in response!")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    debug_single_article()
