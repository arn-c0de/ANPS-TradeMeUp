# 📊 Statistics Tab - Quick Reference

## Layout Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Overall Metrics                                              │
│ Articles | Processed | Entities | Predictions | Impacts | ...  │
├─────────────────────────────────┬───────────────────────────────┤
│ 📈 Event Distribution          │ 🎯 Quality Distribution       │
│ (Bar Chart)                     │ (Histogram)                   │
├─────────────┬──────────────────┼───────────────────────────────┤
│ 🎭 Sentiment│ 💥 Impact        │ 🏢 Top Entities               │
│ (Pie Chart) │ (Bar Chart)      │ (List with Badges)            │
├─────────────┴──────────────────┴───────────────────────────────┤
│ 📊 Entity Sentiment Analysis                [Timeframe: 30d ▾] │
│ (Horizontal Bar Chart - Top 15 by Sentiment Score)             │
├─────────────────────────────────┬───────────────────────────────┤
│ 📈 Top Positive Entities        │ 📉 Top Negative Entities      │
│ #1 Tesla - 12 Pos | 3 Neu | 1 N│ #1 Boeing - 8 Neg | 4 Neu | 1│
│ #2 Apple - 10 Pos | 5 Neu | 2 N│ #2 Meta  - 6 Neg | 3 Neu | 2 │
│ ...                             │ ...                           │
├─────────────────────────────────┴───────────────────────────────┤
│ 🏢 Entity Details                          [Search: _____ ]     │
│ ┌──────────┬──────┬────────┬────────┬────────┬──────────┬────┐ │
│ │ Entity   │ Type │ Ticker │ Ment.  │ Impact │ Avg Imp  │ ... │ │
│ ├──────────┼──────┼────────┼────────┼────────┼──────────┼────┤ │
│ │ Tesla    │ co.  │ TSLA   │ 15 🔵  │ 12 🟢  │ 0.72 🔴  │ ... │ │
│ │ Apple    │ co.  │ AAPL   │ 23 🔵  │ 18 🟢  │ 0.65 🟠  │ ... │ │
│ └──────────┴──────┴────────┴────────┴────────┴──────────┴────┘ │
├─────────────────────────────────────────────────────────────────┤
│ 📰 News Volume Over Time                                        │
│ (Line Chart with Markers)                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Actions

### 📊 View Sentiment Trends
1. Navigate to **Statistics Tab**
2. Scroll to **Entity Sentiment Analysis**
3. Select timeframe: **7d / 30d / 90d / All**
4. View top 15 entities ranked by average sentiment

### 🔍 Search for Specific Entity
1. Scroll to **Entity Details** table
2. Type entity name or ticker in search box
3. View: Mentions, Impact Scores, Average Impact, Metadata
4. Real-time filtering as you type

### 📈 Identify Trending Stocks
**Positive Momentum:**
- Check **Top Positive Entities** (last 30 days)
- Look for high positive count + high avg sentiment
- Cross-reference with **Average Impact** score

**Risk Alert:**
- Check **Top Negative Entities** (last 30 days)
- Monitor entities with many negative articles
- Review **Entity Details** for more context

---

## Color Coding Guide

### Sentiment Colors
- 🟢 **Green**: Positive sentiment (> 0.2)
- ⚪ **Gray**: Neutral sentiment (-0.2 to 0.2)
- 🔴 **Red**: Negative sentiment (< -0.2)

### Impact Score Colors
- 🔴 **Red/Danger**: High impact (≥ 0.7)
- 🟠 **Orange/Warning**: Medium impact (0.4 - 0.7)
- 🔵 **Blue/Info**: Low impact (< 0.4)

### Badge Colors
- 🔵 **Primary**: Mention counts
- 🟢 **Success**: Impact score counts, Positive news
- 🔴 **Danger**: Negative news, Top ranks (#1-3)
- 🟠 **Warning**: Mid ranks (#4-6)
- ⚪ **Secondary**: Neutral news, Low ranks

---

## Data Refresh

- **Auto-Update**: Every 5 seconds via Interval component
- **Manual Refresh**: Reload page or wait for next interval
- **Search Filter**: Updates instantly on input

---

## Key Metrics Explained

### Mentions
Number of news articles mentioning this entity (via Entity Mapping Agent)

### Impact Scores
Number of calculated impact scores for this entity (via Impact Scoring Agent)

### Average Impact
Mean of all impact scores (0-1 scale):
- **0.7+**: High impact (market-moving news)
- **0.4-0.7**: Medium impact (notable news)
- **<0.4**: Low impact (minor mentions)

### Sentiment Score
Average sentiment across all news (-1 to +1 scale):
- **> 0.3**: Very Positive
- **0.1 to 0.3**: Slightly Positive
- **-0.1 to 0.1**: Neutral
- **-0.3 to -0.1**: Slightly Negative
- **< -0.3**: Very Negative

---

## Example Use Cases

### 1️⃣ Daily Market Monitor
**Goal**: See which stocks had most positive/negative news today

**Steps**:
1. Set timeframe to **7d**
2. Check **Top Positive** and **Top Negative** sections
3. Review **Entity Sentiment Chart** for visual ranking
4. Use **Entity Details** to see impact scores

### 2️⃣ Sector Analysis
**Goal**: Compare companies in same sector

**Steps**:
1. Search for first company in **Entity Details**
2. Note: Avg Sentiment, Avg Impact, Mention count
3. Repeat for competitors
4. Cross-reference with **Entity Sentiment Chart**

### 3️⃣ Event Tracking
**Goal**: Monitor specific company after major event

**Steps**:
1. Search company name in **Entity Details**
2. Check mention count and avg impact
3. View position in **Entity Sentiment Chart**
4. Monitor over time with **30d** timeframe

### 4️⃣ Risk Screening
**Goal**: Identify companies with deteriorating sentiment

**Steps**:
1. Check **Top Negative Entities**
2. Look for high negative count AND low avg sentiment
3. Cross-check **Average Impact** (high impact = more serious)
4. Review in **Entity Details** for full context

---

## Database Tables Used

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `entities` | Master list of tracked entities | entity_id, entity_name, entity_type |
| `news_entity_mapping` | Links news to entities | news_id, entity_id, confidence |
| `processed_news` | NLP analysis results | sentiment, event_type, key_facts |
| `impact_scores` | Impact analysis per entity | impact_score, entity_id, news_id |
| `raw_news` | Original news articles | fetched_at, source, content |

---

## Performance Tips

### Large Datasets
- Use **Search** to filter instead of scrolling
- Limit timeframe to **7d** or **30d** for faster loading
- Entity Details shows **top 50** by default

### Slow Chart Loading
- Check network tab in browser DevTools
- Verify DB indexes exist (see STATISTICS_ENTITY_TRACKING.md)
- Consider running pipeline with `--limit` for testing

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search box (browser default) |
| `Tab` | Navigate between timeframe selector and search |
| `Escape` | Clear search (when focused) |

---

**📚 Full Documentation**: [STATISTICS_ENTITY_TRACKING.md](STATISTICS_ENTITY_TRACKING.md)  
**🐛 Issues**: Open GitHub issue with `statistics` label  
**💡 Feature Requests**: Use Discussions or open issue with `enhancement` label
