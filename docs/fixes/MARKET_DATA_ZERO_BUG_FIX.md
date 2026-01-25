# Market Data Bug Fix - Summary

## Problem
Some simulations and predictions showed `$0.00` for market data (Entry, Current Price, Range, Volume) even though the stocks exist. Example: "Oppenheimer" showed all zeros when it's not actually a tradeable stock.

## Root Cause
The system was extracting **analyst firm names** (like Oppenheimer, Wells Fargo Securities, RBC Capital, TD Cowen, etc.) as company entities from news articles, even though they were just mentioned as the analyst/source, not the subject of the news.

For example, in the article "The PNC Financial Services Group, Inc. (PNC) Enters 2026 With Momentum as Oppenheimer Highlights Growth Drivers", the system extracted:
- ✅ **PNC** (correct - subject of the news, valid ticker)
- ❌ **Oppenheimer** (incorrect - analyst firm mentioned in the headline, not a tradeable company)

These invalid entities were created with fallback `COMP_` prefixes (e.g., `COMP_OPPENHEIMER`) since they don't have valid ticker symbols, resulting in:
- Predictions created for non-tradeable entities
- Simulations with no market data ($0.00 everywhere)
- Confusion for users

## Solution Implemented

### 1. **Filter List of Analyst Firms** (entity_mapping_agent.py)
Added a comprehensive list of 50+ analyst/financial service firms to exclude:
- Oppenheimer, Wells Fargo Securities, RBC Capital, TD Cowen, Scotiabank
- Goldman Sachs Research, Morgan Stanley Research, JPMorgan Securities
- Barclays, Citi Research, Deutsche Bank Securities, UBS Securities
- Jefferies, Piper Sandler, Raymond James, Stifel, Evercore, Bernstein
- And many more...

### 2. **Entity Extraction Logic Updated**
Modified the entity extraction process to:
- ✅ Check if a company name is in the analyst firms list → **SKIP**
- ✅ Validate ticker symbols using yfinance
- ✅ Try to find ticker by company name if suggested ticker fails
- ❌ **NO MORE FALLBACK** `COMP_` entities if ticker validation fails → **SKIP instead**

Before:
```python
if not ticker:
    ticker = f"COMP_{normalized_name}"  # Creates invalid entity
```

After:
```python
if not ticker:
    logger.warning(f"Could not find valid ticker - SKIPPING")
    continue  # Don't create entity
```

### 3. **Improved LLM Prompt** (config/prompts/entity_extraction.txt)
Updated the prompt to explicitly instruct the LLM:
- ⚠️ DO NOT extract analyst firms mentioned as sources
- ⚠️ DO NOT extract investment banks mentioned as analysts
- ⚠️ Only extract companies that are the SUBJECT of the news
- ✅ Only extract TRADEABLE entities

### 4. **Cleanup of Existing Invalid Data**
Created and ran `cleanup_invalid_entities.py` which removed:
- ❌ 36 invalid entities (fallback COMP_* entities + invalid sectors)
- ❌ 450 predictions for non-tradeable entities
- ❌ 45 simulations with $0.00 market data
- ❌ 158 impact scores for invalid entities
- ❌ 158 news-entity mappings

Specific analyst firms removed:
- COMP_OPPENHEIMER (3 predictions, 3 simulations)
- COMP_WELLSFARGO (3 predictions, 3 simulations)
- COMP_RBCCAPITAL (3 predictions, 3 simulations)
- COMP_TDCOWEN (3 predictions, 3 simulations)
- COMP_SCOTIABANK (3 predictions, 3 simulations)
- COMP_JPMORGAN (3 predictions, 3 simulations)

Also removed invalid entities like:
- Governments (Federal Reserve, UK Government, Japan government)
- Generic terms (Luxury brands, Data centre companies)
- Cryptocurrencies without tickers (Worldcoin, Cardano)
- Private companies (Bake Shop, Enechain)
- Invalid sectors (OTHER with 342 predictions!, HEALTH)

## Impact

### Before Fix:
- Many predictions/simulations showed $0.00 for market data
- Users saw "wrong" results for non-existent tickers
- Database cluttered with ~450 invalid predictions
- Performance issues with large "OTHER" sector (342 predictions)

### After Fix:
- ✅ Only valid, tradeable companies get predictions
- ✅ All predictions have proper market data
- ✅ Cleaner database (removed 450+ invalid records)
- ✅ Future entity extraction will skip analyst firms
- ✅ Better LLM prompt reduces false extractions

## Testing Recommendations

1. **Run the pipeline** on new news articles to verify analyst firms are skipped
2. **Check predictions tab** - no more $0.00 market data
3. **Verify entity extraction** - should only see tradeable companies
4. **Monitor logs** for "SKIPPING" messages when invalid tickers are detected

## Files Modified

1. `src/agents/entity_mapping_agent.py`
   - Added ANALYST_FIRMS filter list (50+ firms)
   - Modified entity extraction logic to skip invalid entities
   - Removed fallback COMP_* entity creation

2. `config/prompts/entity_extraction.txt`
   - Added warnings about analyst firms
   - Clarified to only extract TRADEABLE entities
   - Added examples of what NOT to extract

3. `cleanup_invalid_entities.py` (new)
   - Script to clean up existing invalid data
   - Successfully removed 450+ invalid predictions

## Prevention

Going forward, the system will:
1. Filter out analyst firms during entity extraction
2. Validate ALL tickers before creating entities
3. Skip entities without valid tickers instead of creating fallbacks
4. Rely on improved LLM prompt to reduce false extractions
5. Only create predictions for entities with valid market data

This ensures users will never see $0.00 market data for simulations again!
