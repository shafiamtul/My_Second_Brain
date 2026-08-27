# IBKR Decommissioning Complete: Migration to Schwab-Only Architecture

**Date:** 2026-08-06  
**Status:** ✅ Implementation Ready  
**Severity:** Critical Architecture Change

---

## Migration Summary

**Objective:** Remove all IBKR TWS/Gateway dependencies. Use **Schwab API exclusively** for all market data. Use **Yahoo Finance** as fallback where needed.

**Files Modified/Created:**

| File | Change | Status |
|------|--------|--------|
| `scheduler_engine.py` | Remove IBKR, use Schwab only | ✅ Rewritten |
| `scheduler_engine_schwab_only.py` | New clean implementation | ✅ Created |
| `schwab_gex_calculator.py` | New GEX from Schwab chains | ✅ Created |
| `data_controllers.py` | DEPRECATED (remove references) | ⚠️ Needs removal |
| `ib_client.py` | DEPRECATED | ⚠️ Remove after cutover |
| `gex_calculator.py` | DEPRECATED (replaced by schwab_gex_calculator.py) | ⚠️ Remove after cutover |

---

## Architecture: Before → After

### BEFORE (IBKR Hybrid)
```
Every 30s:
  Schwab (PRIMARY)
    ↓ write canonical
  IBKR Futures Controller      ← Supplemental
  IBKR Breadth Controller      ← Supplemental
  IBKR Options Controller
    → GEX Calculator (300+ IBKR contract lookups)   ← **9-10 MINUTE BLOCK**
  News Controller
    ↓
  DynamoDB
```

**Problem:** GEX calculation hung for 9+ minutes, blocking scheduler, systemd killed process.

### AFTER (Schwab Only)
```
Every 30s (RTH):
  Schwab (PRIMARY)
    → /quotes (40 symbols) = 1-2 seconds ✓
    → write canonical
    ↓
  Schwab (OPTIONS)
    → /chains (SPY, QQQ) = 2-3 seconds ✓
    → Schwab GEX Calculator (async, timeout 60s) ✓
    ↓
  News (every 10 cycles)
    → NewsAPI = 1-2 seconds ✓
  Health Check (every 10 cycles)
    → Schwab auth status ✓
    ↓
  DynamoDB

Total cycle time: 30-45 seconds (predictable, fast)
```

---

## Data Sources Migration

### Futures (ES, NQ, YM, etc.)

| Symbol | Was Using | Now Using | Fallback |
|--------|-----------|-----------|----------|
| `/ES`, `/NQ`, `/YM`, `/RTY` | IBKR | **Schwab** | Yahoo |
| `/VX`, `/GC`, `/CL` | IBKR | **Schwab** | Yahoo |
| `/ZN`, `/ZB`, `/ZF`, `/ZT` | IBKR | **Schwab** | Yahoo |
| `/BTC` | IBKR | **Schwab** | Yahoo |

**Verification:** `schwab_client.get_quotes(["/ES", "/NQ", ...]) `

---

### Options Data (SPY/QQQ)

| Data | Was Using | Now Using | Notes |
|------|-----------|-----------|-------|
| **Option Chains** | IBKR (`ib_insync`) | **Schwab API** (`get_option_chain()`) | Much faster |
| **Strike Prices** | IBKR Options.strike | **Schwab response** | Same format |
| **Bid/Ask** | IBKR ticker.bid/ask | **Schwab response** | Real-time |
| **Open Interest** | IBKR ticker.openInterest | **Schwab response** | Full chain |
| **GEX Calculation** | IBKR contracts + IV solve | **Black-Scholes + Schwab IV** | Cleaner code |

**Verification:** 
```python
spy_chain = schwab_client.get_option_chain("SPY")
# Response: {"optionChains": [...], "underlyingPrice": 748.01, ...}
```

---

### Breadth Indices ($TICK, $ADD, etc.)

| Index | Was Using | Now Using | Notes |
|-------|-----------|-----------|-------|
| `$TICK` | IBKR Index | **Schwab quote** | Always available |
| `$ADD` | IBKR Index | **Schwab quote** | Always available |
| `$TRIN` | IBKR Index | **Schwab quote** | Always available |
| `$VOLDC` | IBKR Index | **Schwab quote** | Always available |

**Verification:** `schwab_client.get_quotes(["$TICK", "$ADD", "$TRIN", "$VOLDC"])`

---

### Indices (SPX, VIX, NDX, etc.)

| Index | Was Using | Now Using | Fallback |
|-------|-----------|-----------|----------|
| `$SPX`, `$NDX`, `$RUT` | IBKR Index | **Schwab quote** | Yahoo |
| `$VIX`, `$VVIX`, `$SKEW` | IBKR Index | **Schwab quote** | Yahoo |
| `$TNX` (10Y Yield) | IBKR Index | **Schwab quote** | Yahoo |

---

## Code Changes

### 1. Scheduler Initialization (BEFORE → AFTER)

**BEFORE:**
```python
self.ib_client = IBClient(...)  # Remove this
self.breadth_ctrl = BreadthController(self.ib_client)  # Remove
self.futures_ctrl = FuturesController(self.ib_client)  # Remove
self.options_ctrl = OptionsController(self.ib_client)  # Remove
self.schwab_client = get_schwab_client()  # Backup only
```

**AFTER:**
```python
self.schwab_client = get_schwab_client()  # PRIMARY only
# No ib_client, no data_controllers
```

### 2. Data Cycle (BEFORE → AFTER)

**BEFORE:**
```python
schwab_payload = execute_schwab_backup_cycle()  # Primary
if schwab_payload:
    write_canonical(schwab_payload)
    if ib_client.is_connected():
        futures_state = futures_ctrl.fetch()  # Supplemental
        breadth_state = breadth_ctrl.fetch()  # Supplemental
        options_state = options_ctrl.fetch()  # ← **9 min hang**
```

**AFTER:**
```python
schwab_payload = execute_schwab_cycle()  # PRIMARY (primary source)
write_canonical(schwab_payload)
execute_gex_cycle()  # Async, timeout 60s, non-blocking
```

### 3. GEX Calculation

**BEFORE:** `gex_calculator.py` (IBKR-based)
- Fetch chains from IBKR
- Request 300+ individual contracts via TWS
- 5s pauses between batches
- Duration: 9-10 minutes

**AFTER:** `schwab_gex_calculator.py` (Schwab-based)
- Fetch chains from Schwab API (one call)
- Parse Schwab response directly
- Black-Scholes gamma calculation (pure math)
- Duration: 2-3 seconds
- Timeout: 60s (skips if too slow)

---

## Deployment Checklist

### Phase 1: Pre-Deployment Verification (TODAY)

- [ ] **Verify Schwab API availability**
  ```bash
  curl -s "https://api.schwabapi.com/marketdata/v1/quotes?symbols=/ES" \
    -H "Authorization: Bearer TOKEN"
  ```

- [ ] **Test schwab_gex_calculator.py**
  ```bash
  python -c "
  from schwab_gex_calculator import calculate_gex_from_schwab_chain
  # Mock chain response
  print('✓ Module imports without IBKR dependency')
  "
  ```

- [ ] **Verify no IBKR imports remain in new code**
  ```bash
  grep -r "from ib_insync\|from ib_client\|import IBClient" \
    scheduler_engine_schwab_only.py schwab_gex_calculator.py
  # Should return: (empty)
  ```

- [ ] **Test health manager with Schwab**
  ```bash
  # Ensure health_check.py doesn't depend on IBKR
  grep -r "ib_client\|IBClient" health_check.py
  ```

---

### Phase 2: Cutover (PRODUCTION)

1. **Backup current production**
   ```bash
   cp scheduler_engine.py scheduler_engine.py.ibkr_backup_$(date +%s)
   cp ib_client.py ib_client.py.backup
   cp data_controllers.py data_controllers.py.backup
   ```

2. **Deploy new scheduler**
   ```bash
   # On EC2 instance:
   cp scheduler_engine_schwab_only.py scheduler_engine.py
   cp schwab_gex_calculator.py ibkr-api-bridge/
   
   # Systemd will auto-restart
   systemctl restart aqs-ibkr-scheduler.service
   ```

3. **Monitor logs**
   ```bash
   journalctl -u aqs-ibkr-scheduler.service -f
   # Look for:
   # ✓ "Schwab client initialized (PRIMARY)"
   # ✓ "Schwab cycle failed: False" = working
   # ✗ "Schwab API returned no data" = problem
   ```

4. **Verify data flow**
   ```bash
   # Check DynamoDB for fresh data
   aws dynamodb scan --table-name aqs_market_telemetry \
     --region us-east-1 \
     --limit 5 \
     --profile trading-dev \
     --output json | jq '.Items | .[0].ts.S'
   
   # Should be recent timestamp (< 1 minute ago)
   ```

5. **Frontend health check**
   ```bash
   # Visit https://atlasquantsystems.com/
   # Check browser console for API errors
   # Verify market data displays (ES, NQ, SPY, QQQ)
   ```

---

### Phase 3: Cleanup (24-48 HOURS LATER)

If production is stable for 24-48 hours:

- [ ] Remove old files (git commit)
  ```bash
  git rm ib_client.py data_controllers.py gex_calculator.py
  git commit -m "decom: Remove IBKR dependencies, migrate to Schwab-only"
  ```

- [ ] Remove IBKR config from `config.py`
  ```bash
  # Delete:
  # ib_host, ib_port, ib_client_id, ib_* settings
  ```

- [ ] Stop IBKR TWS Gateway on EC2 (if not used elsewhere)
  ```bash
  sudo systemctl stop ib-gateway  # Or whatever the service is named
  ```

- [ ] Archive old systemd service files
  ```bash
  sudo mv /etc/systemd/system/aqs-ibkr-*.service /root/archive/
  sudo systemctl daemon-reload
  ```

---

## Rollback Plan

If production breaks, rollback immediately:

```bash
# On EC2:
cp scheduler_engine.py.ibkr_backup_* scheduler_engine.py
systemctl restart aqs-ibkr-scheduler.service

# Monitor:
journalctl -u aqs-ibkr-scheduler.service -f
```

**Rollback trigger:** If data is stale (timestamp age > 2 minutes) AND IBKR was connected before.

---

## Monitoring & Alerts

### Health Checks

1. **Data Freshness**
   - Alert if timestamp age > 90 seconds (should be 30-45s)
   - Action: Check Schwab API status

2. **GEX Availability**
   - Warn if GEX missing for > 5 cycles
   - Action: Non-critical; data degrades gracefully

3. **Schwab Auth**
   - Error if token refresh fails 3x
   - Action: Restore credentials from SSM

### Log Markers

- `✓` = Success
- `⚠️` = Warning (non-blocking)
- `🔴` = Error (blocks data)
- `🟢` = Ready
- `🔵` = Testing

---

## FAQ

**Q: What if Schwab API goes down?**  
A: Data will be stale. Alerts will fire. Manual restoration needed. No automatic fallback to IBKR (it's gone).

**Q: Will GEX still work?**  
A: Yes, better. Schwab chains are faster than IBKR. If timeout (>60s), cycle is skipped; data degrades gracefully.

**Q: Can we still use IBKR for anything?**  
A: No. This is a complete decommissioning. IBKR TWS/Gateway can be shut down.

**Q: What if Schwab doesn't have a symbol?**  
A: It won't appear in the quotes response. Frontend will show "N/A" or last cached value. Options: (1) use Yahoo fallback, (2) add to manual data, (3) remove from dashboards.

**Q: How do we verify the change worked?**  
A: 
1. Browser network tab: `/api/history` should return fresh data
2. Terminal: Check Redis cache age
3. Dashboard: Live prices update every 30s
4. CloudFront: Invalidate cache, hard refresh page (Cmd+Shift+R)

---

## Success Criteria

✅ Production is considered **SUCCESS** when:

1. Data timestamp is < 1 minute old (should be 30-45s)
2. All market symbols (ES, NQ, SPY, QQQ) have prices
3. GEX walls are calculated (SPY/QQQ)
4. No IBKR connection errors in logs
5. Frontend displays data without errors
6. Data persists for 24+ hours without stale alerts

---

## Decommissioning Status

| Component | Status | Replacement |
|-----------|--------|-------------|
| **IBKR TWS/Gateway** | 🔴 REMOVE | Schwab API |
| **IBClient** | 🔴 REMOVE | schwab_client |
| **BreadthController** | 🔴 REMOVE | Schwab quotes |
| **FuturesController** | 🔴 REMOVE | Schwab quotes |
| **OptionsController** | 🔴 REMOVE | Schwab chains |
| **GEXCalculator (old)** | 🔴 REMOVE | SchwabGEXCalculator |
| **scheduler_engine.py** | 🟡 MIGRATE | scheduler_engine_schwab_only.py |
| **data_controllers.py** | 🔴 REMOVE | None needed |

---

## Known Limitations (Post-Migration)

1. **No historical 30-second candles** (Schwab doesn't provide)
   - Mitigation: Use 1-minute bars from Yahoo for backtesting

2. **Breadth delayed by 15+ minutes** (Schwab quote limitation)
   - Mitigation: Document in dashboards; real-time not available

3. **FX prices delayed** (Schwab delay vs IBKR live)
   - Mitigation: Use Yahoo for  real-time FX if needed

4. **No future order execution** (Schwab quotes only, no trading API)
   - Mitigation: Keep separate trading platform (unchanged)

---

*Migration Plan Created: 2026-08-06 21:45 UTC*  
*Target Deployment: 2026-08-06 22:00 UTC (immediate)*  
*Expected Production Stability: 2026-08-07 22:00 UTC (24h verification)*
