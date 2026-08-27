# IBKR TWS API Bridge

A lightweight, local Python-based service that connects to Interactive Brokers Trade Workstation (TWS) or IB Gateway, gathers account/position data, and bridges it to your external systems.

It supports two primary deployment architectures:
1. **Local REST API Mode (Uvicorn/FastAPI)**: Serves a local JSON API on port `8000` for local agents or VPNs.
2. **AWS Cloud Relay Mode (boto3 Daemon)**: Periodically polls TWS and pushes encrypted JSON snapshots directly to your **AWS S3 bucket**, making the data safely and continuously accessible to your AWS-hosted AQS website/portal without exposing your local machine or firewalls to the public internet.
3. **VSCCC & AWS Bedrock Swarm Mode**: Integrates parallel specialized sub-agents powered by **AWS Bedrock (Claude 3.5 Sonnet)** adhering to Karpathy first-principles software discipline.
4. **AWS DynamoDB Modular Relay**: Batches and writes compiled market data categories (Breadth, Futures, Options) directly to AWS DynamoDB (`aqs_market_telemetry`) with sub-second RTH (Regular Trading Hours) and ETH (Extended Trading Hours) session-aware scheduling.

---

## Prerequisites

1. **Python 3.8+**
2. **Interactive Brokers TWS or IB Gateway** running and logged in.
3. **Configure TWS API settings**:
   - Open TWS, go to **Global Configuration** -> **API** -> **Settings**.
   - Enable **"Enable ActiveX and Socket Clients"**.
   - Note the **Socket port** (default: `7497` for paper trading, `7496` for live trading).
   - Ensure the IP address `127.0.0.1` is added to the "Trusted IPs" list.

---

## Installation

Create a virtual environment and install the required dependencies:

```bash
# Navigate to the bridge folder
cd ibkr-api-bridge

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Customize settings by creating a `.env` file in the `ibkr-api-bridge/` folder:

```ini
# --- IBKR TWS Connection ---
IB_BRIDGE_IB_HOST=127.0.0.1
IB_BRIDGE_IB_PORT=4002
IB_BRIDGE_IB_CLIENT_ID=99

# --- Local API Server ---
IB_BRIDGE_API_PORT=8000
IB_BRIDGE_API_TOKEN=your_secure_agent_token  # Set this to require 'X-API-Token' header

# --- AWS S3 Cloud Relay & Bedrock ---
IB_BRIDGE_AWS_ACCESS_KEY_ID=your_aws_access_key
IB_BRIDGE_AWS_SECRET_ACCESS_KEY=your_aws_secret_key
IB_BRIDGE_AWS_REGION=us-east-1
IB_BRIDGE_AWS_S3_BUCKET=aqs-market-data-bucket
IB_BRIDGE_AWS_S3_KEY=live/ibkr_trading_state.json
IB_BRIDGE_AWS_S3_ENCRYPTION=AES256
IB_BRIDGE_RELAY_INTERVAL_SECONDS=30
IB_BRIDGE_GEX_SYMBOLS=SPX,NDX
```

For cloud deployment, store `IB_PASSWORD` and `IB_TOTP_SECRET` as SSM SecureString
or Secrets Manager values and inject them into the EC2 host at runtime. Never
commit those values to `.env` or `docker-compose.yml`.

---

## Running the Application

### 1. Test Connection
Test socket communication with TWS:
```bash
python test_conn.py
```

### 2. Run AWS Cloud Relay Daemon (Option 1 - Recommended)
Periodically pushes TWS snapshots up to AWS S3:
```bash
python cloud_relay.py
```

The relay publishes a single encrypted JSON snapshot to
`s3://aqs-market-data-bucket/live/ibkr_trading_state.json` every 30 seconds. The
Phase 2 schema includes account summary, positions, `volatility_index`,
`market_internals`, naive `gex_metrics`, and `freshness_check` telemetry. If IBKR
is disconnected, the relay uploads an explicit offline payload instead of going
silent.

### 3. Run VSCCC & AWS Bedrock Parallel Swarm
Invokes specialized sub-agents (Harvester, GEX Math, Macro Surprise, Telemetry Sensor) using Claude 3.5 Sonnet on AWS Bedrock:
```bash
# Test with dry-run mode
python bedrock_swarm.py --dry-run

# Run full live invocation
python bedrock_swarm.py
```

### 4. Run Quality & Telemetry Sensor Suite
Enforces numeric sanity bounds ($VIX \in [5, 150]$, $ADD \in [-3500, +3500]$) and data freshness checks:
```bash
python telemetry_sensors.py
```

### 5. Run Session-Aware DynamoDB Scheduler
Executes modular category polling (RTH/ETH) and writes to AWS DynamoDB:
```bash
# Test run with local mock database writes
python scheduler_engine.py --test-run

# Run live production scheduler
python scheduler_engine.py
```

---

## VSCCC & AWS Bedrock Swarm Architecture

The Bedrock Swarm Framework runs four specialized agents concurrently in parallel worker pools:

* **Harvester Agent** (`karpathy_prompts.py`): Evaluates raw market breadth and tick dynamics ($ADD, $VOLD, $TRIN).
* **GEX Math Agent**: Computes 0DTE SPX/NDX options strike gamma, major call/put walls, and zero-gamma flip points.
* **Macro Surprise Agent**: Evaluates actual vs. forecast economic prints ($\text{Actual} - \text{Forecast}$) and assesses dovish/hawkish risk framing.
* **Telemetry Sensor Agent**: Evaluates data freshness, payload completeness, and operational health.
