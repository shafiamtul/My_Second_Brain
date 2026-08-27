# IBKR vs Schwab: Data Source Audit

## Executive Summary

**PROBLEM:** The architecture states **Schwab is PRIMARY**, but we're still running expensive IBKR operations every 30 seconds that weren't planned to be production features.

**Current Status:** ⚠️ **MISALIGNED** - GEX calculation was a "pending" feature but runs every cycle and crashed the scheduler.

---

## Data Source Architecture

### Intended (From automationStatus.ts)

| Data | Status | Source | Notes |
|------|--------|--------|-------|
| **Futures (40 symbols)** | ✅ Delivered | **Schwab PRIMARY** | ES, NQ, YM, etc. |
| **Breadth indices** | ✅ Delivered | **Schwab PRIMARY** | Advance/decline, new highs/lows |
| **News** | ✅ Delivered | NewsAPI | 10 articles per cycle |
| **SPX DIX/GEX (daily)** | ✅ Delivered | SqueezeMetrics CSV | Daily dealer-flow proxy only |
| **Direct ES/NQ GEX (intraday)** | ⚠️ **PENDING** | Evaluate vendors | NOT production yet |

### Actual (What's Running Now)

| Data | Source | Frequency | Used? |
|------|--------|-----------|-------|
| Futures | **Schwab (primary)** → IBKR (supplemental) | Every 30s RTH | ✅ Yes |
| Breadth | **Schwab (primary)** → IBKR (supplemental) | Every 30s RTH | ✅ Yes |
| News | NewsAPI | Every 5 min | ✅ Yes |
| **SPY/QQQ GEX walls** | **IBKR (via gex_calculator.py)** | **Every 30s RTH** | ✅ Yes |
| PCR (Put/Call ratio) | **IBKR** | **Every 30s RTH** | ✅ Yes |

---

## The IBKR Problem

### What We're Querying from IBKR Every 30 Seconds

```python
# scheduler_engine.py, execute_data_sync_cycle()
options_state = await self.options_ctrl.fetch_state()
  ↓
# data_controllers.py, OptionsController.fetch_state()
calc = GEXCalculator(self.ib)
result = await calc.fetch_snapshot_dual(["SPY", "QQQ"])
  ↓
# gex_calculator.py, GEXCalculator.fetch_snapshot_dual()
for symbol in ["SPY", "QQQ"]:
  - Fetch option chains (0DTE + next 44 days)
  - Select 45 strikes × 2 sides = 90 contracts per expiry
  - Request bid/ask/OI for EACH contract (300+ individual API calls)
  - Calculate implied volatility
  - Compute Black-Scholes gamma
  - Aggregate into GEX walls (PG, ZG, NG)
```

**Result of last crash (20:34:45):**
- Process: 9 minutes 54 seconds stuck fetching options
- CPU: 6 min 11 sec consumed
- Reason: 300+ IBKR contract lookups with 5s pauses between batches

---

## Why This Is Wrong

### 1. **Schwab Has Options Chains Too**

```python
# schwab_client.py has this method (not being used):
def get_option_chain(self, symbol: str, contractType: str = "ALL", 
                      rangeType: str = "ALL", strikeCount: Optional[int] = None):
    """Queries Schwab chains API for options structures."""
    url = f"https://api.schwabapi.com/marketdata/v1/chains?..."
    return self.request("GET", url, timeout=15)
```

**Status:** Method exists but **NEVER CALLED** in the codebase.

---

### 2. **GEX Was Supposed to Be "Pending"**

From [public-site/src/data/automationStatus.ts](public-site/src/data/automationStatus.ts#L76-L80):

```typescript
{
  category: "Data",
  item: "Direct ES/NQ intraday GEX",
  status: "pending",  // ← NOT PRODUCTION
  delivered: "None; current GEX is SPX daily proxy plus VIX/VVIX/SKEW.",
  pending: "Evaluate SpotGamma, Cboe/options-data, or a futures/options vendor.",
}
```

**Translation:** GEX should be optional/fallback, not a required every-30-seconds operation.

---

### 3. **Architecture Says Schwab is PRIMARY**

From scheduler_engine.py (lines 260-278):

```python
async def execute_priority_cycle(self, rth_active: bool):
    # PRIMARY DATA SOURCE: Schwab API (40 symbols)
    schwab_payload = await self.execute_schwab_backup_cycle(...)
    
    if schwab_payload:
        # Write Schwab as CANONICAL (primary source)
        self.db_relay.write_canonical_rows(schwab_payload)
        
        # SECONDARY: IBKR supplements only if connected
        if self.ib_client.is_connected():
            await self.execute_data_sync_cycle(...)  # ← IBKR as fallback
```

**But then:**

```python
async def execute_data_sync_cycle(self, rth_active: bool, ...):
    # 4. Fetch & Write Options GEX Levels (Runs always: 30s in RTH)
    options_state = await self.options_ctrl.fetch_state()
```

**The problem:** GEX is in `execute_data_sync_cycle()`, making it **secondary/fallback**, but it runs **every 30 seconds as if it's primary**.

---

## What Should Happen

### Current Flow (Wrong)
```
Every 30s:
  1. Fetch Schwab data (40 symbols) ✅ Primary — fast, 1-2 seconds
  2. Write Schwab as canonical ✅
  3. IF IBKR connected:
     a. Fetch IBKR futures (supplemental) ✅ 
     b. Fetch IBKR breadth (supplemental) ✅
     c. Fetch IBKR GEX (9+ minutes!) ⚠️ BLOCKS EVERYTHING
     d. Fetch news (supplemental) ✅
```

### Correct Flow (Proposed)
```
Every 30s:
  1. Fetch Schwab data (40 symbols) ✅ PRIMARY — fast
  2. Write Schwab as canonical ✅
  3. IF IBKR connected AND rth_active:
     a. Fetch IBKR futures (supplemental) ✅
     b. Fetch IBKR breadth (supplemental) ✅
     c. IF time_budget_allows AND gex_not_running:
        - Fetch Schwab options chain (primary) ✅ OR skip GEX this cycle
     d. Fetch news every 10 cycles (not every cycle) ✅

Every 5 min (async GEX daemon, separate from primary scheduler):
  - Calculate GEX from Schwab chains OR IBKR
  - Don't block primary data collection
  - Timeout after 60 seconds if hung
```

---

## Full IBKR Dependency List

### IBKR Used For:

1. **Futures Data** (supplemental)
   - Source: `FuturesController.fetch_state()`
   - Symbols: ES, NQ, YM, RTY, ZN, ZB, GC, SI, BTC, CL
   - Time: ~2-3 seconds
   - Priority: ⚠️ Supplemental (Schwab provides same data faster)

2. **Breadth Data** (supplemental)
   - Source: `BreadthController.fetch_state()`
   - Metrics: Advance/decline, new highs/lows
   - Time: ~1-2 seconds
   - Priority: ⚠️ Supplemental (could use Schwab)

3. **GEX/Gamma Data** (supplemental but expensive)
   - Source: `OptionsController.fetch_state()` → `GEXCalculator`
   - Symbols: SPY 0DTE + OI, QQQ 0DTE + OI
   - Time: **9-10 minutes** ⚠️⚠️⚠️
   - Priority: ⚠️ SHOULD BE OPTIONAL (marked "pending")
   - **← THIS CAUSED THE CRASH**

---

## Root Cause of Crash

| Layer | Issue | Impact |
|-------|-------|--------|
| **Architecture** | GEX marked "pending" but runs every 30s | Unnecessary load |
| **Implementation** | GEX uses IBKR (not Schwab chains) | IBKR doesn't scale |
| **Algorithm** | 300+ sequential API calls with 5s pauses | 9-10 minutes per cycle |
| **Integration** | GEX blocks primary data cycle | Scheduler stalls, systemd kills it |
| **Monitoring** | No timeout on GEX calculation | Process runs to death |

---

## Audit Results: Are We Still Querying IBKR?

### ✅ IBKR Queries That Make Sense
1. Futures (but slow compared to Schwab)
2. Breadth (but available from Schwab)

### ⚠️ IBKR Queries That Shouldn't Happen
1. **GEX calculation** — marked "pending", runs every 30s, caused crash
2. **Options chains** — Schwab has these (unused method), IBKR doesn't scale

### 🚫 Should Never Happen
- Block primary Schwab data fetch with experimental IBKR features

---

## Recommendations (Priority Order)

### IMMEDIATE (Today)
1. ✅ **Skip GEX every 30s** — Move to async daemon running every 2-5 minutes
2. ✅ **Add GEX timeout** — Kill if > 60 seconds, skip that cycle
3. ✅ **Add circuit breaker** — If GEX fails 3x, disable for 30 minutes

### SHORT-TERM (This Week)
1. Test Schwab options chain API (`get_option_chain()`)
2. Replace IBKR GEX with Schwab GEX if Schwab chains have enough data
3. Document which data REALLY needs IBKR vs what Schwab provides

### MEDIUM-TERM (Next 2 Weeks)
1. Separate GEX into independent daemon
2. Primary scheduler: Schwab only (~30s cycle)
3. GEX daemon: Schwab or IBKR options (~120-300s cycle)
4. Add watchdog: Monitor data freshness, auto-restart if stale

### LONG-TERM (Roadmap)
1. Evaluate SpotGamma/Cboe options-data per automation plan
2. Migrate away from IBKR for non-essential features
3. Use Schwab as single source of truth (faster, more reliable)

---

## Conclusion

**Current State:** ⚠️ Misaligned  
**Severity:** 🔴 High (crashed today)  
**Fix Complexity:** 🟡 Medium (requires async refactor)  
**Business Impact:** 🔴 High (10 min data stalls)

**Action:** Skip GEX from primary cycle, move to async daemon, add timeout.

---

*Audit completed: 2026-08-06 21:15 UTC*  
*Last incident: Scheduler crashed at 20:34:45 UTC after 9m 54s GEX calculation*
