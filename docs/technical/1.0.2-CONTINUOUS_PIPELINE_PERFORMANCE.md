# Continuous Pipeline - Performance & Hardening Guide

## 🚀 Performance-Optimierungen

### 1. **Dynamische Batch-Größen**
Das System passt Batch-Größen automatisch an die Performance an:

```python
# Initial Batch Sizes
quality: 50 articles
content: 10 articles  
entity: 10 articles
surprise: 20 articles
impact: 20 articles
prediction: 50 predictions

# Auto-Anpassung:
# - Iteration >5 min → Batch-Größen um 20% reduzieren
# - Iteration <2 min & keine Fehler → Batch-Größen um 20% erhöhen
# - Max Limits: quality=100, content=20, entity=20, surprise=50, impact=50, prediction=100
```

### 2. **Memory Monitoring & Garbage Collection**
```bash
# Standard: 2GB Memory Limit
python scripts/run_continuous_pipeline.py

# Erhöhtes Limit für große Datenmengen
python scripts/run_continuous_pipeline.py --max-memory 4096  # 4GB

# Aggressiver Modus
python scripts/run_continuous_pipeline.py --max-memory 8192  # 8GB
```

**Features:**
- Kontinuierliches Memory-Monitoring mit `psutil`
- Automatisches Garbage Collection bei Überschreitung
- Memory-Delta Tracking pro Iteration

### 3. **Performance Metrics**
```
=============================================================
Pipeline Iteration #5 - 2026-01-23 04:30:15
Memory: 892.3MB | Avg Time: 124.5s | Batch Sizes: {'quality': 60, 'content': 12, ...}
=============================================================

...

Iteration #5 completed in 118.2s (avg: 124.5s)
Memory delta: +12.3MB (now: 904.6MB)
```

**Tracked Metrics:**
- Durchschnittliche Iterationszeit (Rolling Average über 20 Iterationen)
- Min/Max Iterationszeiten
- Memory-Nutzung (vor/nach Iteration)
- Fehlerrate (total & consecutive)

## 🛡️ Hardening Features

### 1. **Graceful Shutdown**
```python
# Signal Handling
SIGINT (Ctrl+C)  → Graceful Shutdown
SIGTERM          → Graceful Shutdown
```

**Shutdown-Prozess:**
1. Signal empfangen
2. Aktuelle Iteration abschließen
3. DB-Verbindungen schließen
4. Statistiken loggen
5. Sauber beenden

### 2. **Exponential Backoff bei Fehlern**
```python
# Error Recovery Logic
Fehler 1: 5s wait
Fehler 2: 10s wait
Fehler 3: 20s wait
Fehler 4: 40s wait
Fehler 5+: 600s wait (10 min)

# Max Backoff: 5 Minuten (außer bei >5 consecutive errors)
```

### 3. **DB Connection Retry Logic**
```python
# 3 Versuche mit exponential backoff
Versuch 1: Sofort
Versuch 2: Nach 2s
Versuch 3: Nach 4s
# Dann: Exception werfen
```

### 4. **Garantierte Ressourcen-Freigabe**
```python
try:
    # Pipeline Iteration
except Exception:
    # Error Handling
finally:
    # DB Session IMMER schließen
    if self.db:
        self.db.close()
        self.db = None
```

## 📊 Monitoring

### Log-Output Beispiel
```
2026-01-23 04:15:30 - __main__ - INFO: Pipeline initialized with max_memory=2048MB, check_interval=300s
2026-01-23 04:15:30 - __main__ - INFO: Starting continuous pipeline (check every 300s)

=============================================================
Pipeline Iteration #1 - 2026-01-23 04:15:30
Memory: 445.2MB | Avg Time: 0.0s | Batch Sizes: {'quality': 50, 'content': 10, ...}
=============================================================

[Phases 1-8 durchlaufen...]

Iteration #1 completed in 142.3s (avg: 142.3s)
Memory delta: +12.1MB (now: 457.3MB)

Found 15 items pending (assessed:5, analyzed:3, mapped:2, surprised:2, scored:2, predicted:1)
Continuing immediately to process backlog...
```

### Error Handling Beispiel
```
2026-01-23 04:20:15 - __main__ - ERROR: Error in pipeline iteration #3 (consecutive: 1): Connection timeout
2026-01-23 04:20:15 - __main__ - WARNING: Backing off for 5s before retry (consecutive errors: 1)

[5 Sekunden Pause]

2026-01-23 04:20:20 - __main__ - INFO: Starting Pipeline Iteration #4
```

### Shutdown Statistiken
```
2026-01-23 06:30:45 - __main__ - INFO: Stopping continuous pipeline...
2026-01-23 06:30:45 - __main__ - INFO: Closing database connection...
2026-01-23 06:30:45 - __main__ - INFO: Pipeline Statistics:
2026-01-23 06:30:45 - __main__ - INFO:   - Total Errors: 3
2026-01-23 06:30:45 - __main__ - INFO:   - Avg Iteration Time: 138.7s
2026-01-23 06:30:45 - __main__ - INFO:   - Min/Max Iteration: 98.2s / 245.3s
2026-01-23 06:30:45 - __main__ - INFO: Shutdown complete.
```

## ⚙️ Configuration Best Practices

### Development Mode
```bash
# Schnelle Iterations, moderate Batches
python scripts/run_continuous_pipeline.py \
  --interval 120 \      # 2 Minuten
  --max-memory 2048     # 2GB
```

### Production Mode
```bash
# Standard Produktion
python scripts/run_continuous_pipeline.py \
  --interval 300 \      # 5 Minuten
  --max-memory 4096     # 4GB
```

### High-Volume Mode
```bash
# Viele News-Quellen, aggressive Processing
python scripts/run_continuous_pipeline.py \
  --interval 60 \       # 1 Minute
  --max-memory 8192     # 8GB
```

### Low-Resource Mode
```bash
# Begrenzte Resources (VPS, Raspberry Pi, etc.)
python scripts/run_continuous_pipeline.py \
  --interval 600 \      # 10 Minuten
  --max-memory 1024     # 1GB
```

## 🔍 Troubleshooting

### Memory Leak Detection
```bash
# Wenn Memory stetig steigt:
1. Log prüfen: "Memory delta: +X MB"
2. Wenn stetig positiv → Memory Leak
3. Lösung: max-memory reduzieren für häufigere GC
```

### Performance-Probleme
```bash
# Wenn Iterationen zu langsam:
1. Log prüfen: "Iteration completed in X s (avg: Y s)"
2. System passt Batch-Größen automatisch an
3. Manual: --interval erhöhen für weniger Last
```

### Zu viele Fehler
```bash
# Wenn consecutive errors >5:
1. System geht in 10-min Backoff
2. Check: LLM API Limits, DB Connection, Network
3. Nach Fix: System recovered automatisch
```

### Stuck Pipeline
```bash
# Wenn Pipeline "hängt":
1. Ctrl+C → Graceful Shutdown (wartet auf Iteration Ende)
2. Wenn nicht reagiert: Kill Signal
3. DB Sessions werden automatisch freigegeben
```

## 📈 Performance Benchmarks

### Typische Werte (OpenAI GPT-3.5-turbo, SQLite)

| Phase | Batch Size | Time/Batch | Articles/Hour |
|-------|-----------|-----------|---------------|
| Phase 2: Quality | 50 | 2-5s | ~36,000 |
| Phase 3: Content | 10 | 30-60s | ~600 |
| Phase 4: Entity | 10 | 40-80s | ~450 |
| Phase 7: Impact | 20 | 1-2s | ~36,000 |
| Phase 8: Predictions | 50 | 1-3s | ~60,000 |

**Bottleneck:** Phase 3 & 4 (LLM Calls)

### Optimierungen für Durchsatz

1. **Parallele LLM Calls** (TODO)
   - Aktuell: Seriell
   - Potential: 10x Speedup mit asyncio

2. **LLM-Provider Wechsel**
   - OpenAI gpt-3.5: ~5s/article
   - OpenAI gpt-4: ~15s/article
   - Ollama (lokal): ~30-60s/article
   - Anthropic Claude: ~3-8s/article

3. **Caching** (TODO)
   - Redis-Cache für Entity-Lookups
   - Embedding-Cache für ähnliche Articles
   - Regime-Detection Cache (5-min TTL)

## 🔒 Security Hardening (Geplant)

- [ ] Rate Limiting für LLM APIs
- [ ] Input Validation & Sanitization
- [ ] Secure DB Connection Pooling
- [ ] Audit Logging
- [ ] API Key Rotation
- [ ] Health Check Endpoint

---

**Version:** 1.0.0  
**Last Updated:** January 23, 2026  
**Status:** Production Ready ✅
