"""Check article quality - how many are real financial news?"""

from sqlalchemy import create_engine, text

from src.config.settings import settings

engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Get sample of articles without entity mappings
    result = conn.execute(text("""
        SELECT 
            rn.title,
            rn.source,
            pn.event_type,
            pn.sentiment
        FROM raw_news rn
        LEFT JOIN processed_news pn ON rn.news_id = pn.news_id
        LEFT JOIN news_entity_mapping nem ON rn.news_id = nem.news_id
        WHERE nem.news_id IS NULL
        AND pn.news_id IS NOT NULL
        ORDER BY rn.published_at DESC
        LIMIT 50
    """))

    articles = result.fetchall()

    print("="*80)
    print(f"📰 SAMPLE OF {len(articles)} ARTICLES WITHOUT ENTITY MAPPINGS")
    print("="*80)

    non_financial = []

    for i, (title, source, event_type, sentiment) in enumerate(articles, 1):
        # Check if it's financial news
        crossword = 'crossword' in title.lower()
        podcast = 'podcast' in title.lower()
        ft_live = 'ft live' in title.lower()

        if crossword or podcast or ft_live:
            non_financial.append(title)
            marker = "❌ NON-FINANCIAL"
        else:
            marker = "✅ FINANCIAL"

        print(f"\n{i}. {marker}")
        print(f"   Title: {title[:80]}")
        print(f"   Source: {source}")
        print(f"   Event: {event_type}, Sentiment: {sentiment}")

    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total Sample: {len(articles)}")
    print(f"Non-Financial (Crosswords/Podcasts): {len(non_financial)}")
    print(f"Likely Financial: {len(articles) - len(non_financial)}")
    print(f"Percentage Financial: {(len(articles) - len(non_financial)) / len(articles) * 100:.1f}%")

    if non_financial:
        print(f"\n⚠️ NON-FINANCIAL ARTICLES ({len(non_financial)}):")
        for title in non_financial[:10]:
            print(f"  - {title}")
