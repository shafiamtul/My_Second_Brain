# Atlas Quant Systems (AQS) Unified Telemetry & Logging Schema

This document defines the **Standard Engineering Telemetry Schema** for all Atlas Quant Systems daily trading runbooks, deployment logs, and script outputs. Adhering to this layout ensures that both the **VSC-CC builder engine** (Claude Code) and **Google Antigravity** can read, parse, and visually structure operational logs identically.

---

## 1. Key Formatting Guidance
1. **No Absolute Local Passwords/Keys:** All API Secrets, Database Tokens, or private AWS URLs must be masked (e.g. `******-[four-digit-suffix]`).
2. **Standard Timezone:** All timestamps **MUST** be recorded in **UTC (ISO 8601)** or **EST**, with explicit indicators.
3. **P.A.R.A Alignment:** Telemetry blocks appended to runbooks automatically invoke the `indexer.py` script so that horizontal links propagate instantly inside the Second Brain.

---

## 2. Standard Telemetry Markdown Block

Every execution report or deployment snapshot must output the following three tables to standardize diagnostic aggregation:

### I. Execution Metadata
| Metric | Value | Notes / Description |
| :--- | :--- | :--- |
| **Timestamp** | `2026-08-27 03:15:00 UTC` | Current execution datetime in UTC |
| **System Host** | `EC2 (i-073339a060355bf96)` | Core EC2 host machine or deployment portal |
| **Script/Process** | `schwab_breadth_fetcher.py` | Executed module filename or shell task |
| **Trigger Origin** | `Systemd (aqs-ibkr-scheduler)` | Systemd, Cron, Manual, AWS CodePipeline |
| **Execution Status** | `SUCCESS` | `SUCCESS` \| `FAILURE` \| `WARNING` |
| **Exit Code** | `0` | standard shell process return value |
| **Duration (secs)** | `1.423s` | Total execution run time in seconds |

### II. Core System & Data Layer Checklist
| Integration Horizon | Health Indicator | Last Latency | Gateway Endpoint State |
| :--- | :---: | :--- | :--- |
| **Schwab OAuth Ingestion** | ✅ ON-LINE | 350ms | `/aqs/schwab/tokens` (SSM Parameter State Verified) |
| **Local Redis Cache** | ✅ ON-LINE | 8ms | port `6379` (`aqs:snapshot` verified) |
| **AWS DynamoDB Storage** | ✅ ON-LINE | 45ms | DB Table: `aqs_market_telemetry` |
| **FastAPI REST API (EC2)** | ✅ ON-LINE | 12ms | port `8000` (`/api/history` serving 200 OK) |
| **CloudFront Distrib.** | ⚡ STALE-CLEARED | — | Invalidation ID: `I1O0XYZAB123` cleared paths: `/*` |

### III. Active Risk, Position & Capital Constraints
| Parameter | Configuration Limit | Current State | Risk Indicator / Health |
| :--- | :--- | :--- | :--- |
| **Base Currency / Capital**| $100,000.00 | $104,250.00 | 104.25% (Bullish Accrual) |
| **Daily Drawdown Cap** | Max -2.5% (-$2,500.00) | -$120.00 | 0.12% Drawdown Active (Safe) |
| **Max Portfolio Slices** | 8 concurrent contracts | 2 active | 25.0% In-Use (Safe) |
| **RTH Tick Volume Lock** | Volatility Max 40% | VIX 16.5 | Trade Conditions Normal |

---

## 3. Telemetry Integration (YAML Front-Matter Config)

Under certain automated workflows (like indexers or telemetry scrapers), append this YAML header block at the extreme beginning of runbooks:

```yaml
---
telemetry_version: 1.0.0
system_code: aqs-market-data-bridge
parent_node: "[[3_Resources/AQS_Project_Docs/index]]"
last_health_state: GREEN
---
```

---

## 4. Runbook Entry Template Examples

### Example A: Successful Deployment Execution
```markdown
### ✅ [2026-08-27 03:15:00 UTC] Task: Deploy Frontend Production Site
* **Status:** SUCCESS
* **Directory Context:** `1_Projects`
* **Trigger:** AWS S3 CodeBuild Webhook

<details>
<summary>🔍 Expand Deployment Metrics</summary>

| Metric | Delta Value | Health Check Status |
| :--- | :--- | :---: |
| **Static Output Generation** | 45 static HTML files generated | ✅ Passed |
| **S3 Sync Speed** | 12.3MB synced at 45MB/s | ✅ Passed |
| **CloudFront Invalidation** | Paths: `/*` triggered | ✅ Completed |

</details>
```

### Example B: Failed Script Run Detection
```markdown
### ❌ [2026-08-27 03:18:22 UTC] Task: Schwab Token Refresh
* **Status:** FAILURE
* **Directory Context:** `2_Areas`
* **Trigger:** scheduler_engine.py daemon (30s Tick)

<details>
<summary>🔍 Expand Errors & Diagnostic Stack</summary>

| Inbound Trigger | Error Code | Outbound Impact |
| :--- | :--- | :--- |
| **Schwab OAuth Refresh** | `400 Bad Request` | OAuth token expired and direct refresh locked |

```python
# Error Code Stack Frame Trace:
ValueError: "Unable to retrieve token from sso: Token has expired and refresh failed."
  at TokenManager._refresh_schwab_credentials (schwab_api_gate.py:92)
  at IngestionLoop.run (scheduler_engine.py:121)
```

</details>
```
