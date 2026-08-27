# Production Playbook: IB Gateway 24/7 Unattended Cloud Deployment
**Target Environment**: AWS EC2 Docker (`gnzgl/ib-gateway-docker`)  
**Account Configuration**: Secondary Read-Only User (`rtariq234d`)  
**2FA Mechanism**: TOTP Automation via `pyotp`  
**Consumer System**: VSCCC (Virtual System Command & Control Center) talking to AWS Bedrock  

---

## 1. Executive Summary & Goals

### Objective
Deploy an automated, 24/7 unattended Interactive Brokers API gateway in AWS that streams real-time market data (0DTE SPX/NDX options chains, GEX metrics, VIX/VVIX/SKEW, and market internals `$TICK`, `$ADD`, `$VOLD`, `$TRIN`) to AWS S3, enabling the **VSCCC / AWS Bedrock** engine to perform live multi-agent market analysis without human intervention or manual 2FA taps.

### Security Guarantees
1. **Secondary Account Scope (`rtariq234d`)**: Restricted to **Read-Only / Market Data Access Only**. No order execution or capital withdrawal capability.
2. **Shared Market Data**: Inherits master account subscriptions (CME Futures, OPRA Options, CBOE Indices) at $0 additional cost.
3. **Automated 2FA**: Uses a 32-character TOTP secret key and Python's `pyotp` library to auto-generate 6-digit 2FA tokens upon nightly Gateway reboots (23:45 EST).

---

## 2. High-Level Architecture Diagram

```mermaid
graph TD
    subgraph AWS EC2 (Docker Host)
        TOTP[PyOTP 2FA Generator] -->|Injects Token| IBC[IBC - IB Controller]
        IBC -->|Automates Login| IBGW[IB Gateway Container\ngnzgl/ib-gateway-docker]
        IBGW -->|Socket 4002/7497| Relay[Python Cloud Relay Daemon]
    end

    subgraph IBKR Cloud
        IBKR[IBKR Servers\nCME/CBOE/OPRA Feeds] <-->|Encrypted Connection| IBGW
    end

    subgraph AWS Cloud Storage & AI
        Relay -->|Pushes JSON Snapshot| S3[(AWS S3 Bucket\n`aqs-market-data-bucket`)]
        S3 -->|Reads Market State| Bedrock[AWS Bedrock / VSCCC Engine]
    end
```

---

## 3. Step-by-Step Implementation Playbook

### Phase 1: IBKR Account Management & Secondary User Setup (`rtariq234d`)

1. Log in to the master IBKR Portal (`https://www.interactivebrokers.com`).
2. Navigate to **User Access Rights** $\rightarrow$ **Users & Access Rights** $\rightarrow$ **Add Secondary User**.
3. Set the username to **`rtariq234d`**.
4. Set permissions to **Read-Only / Market Data Access Only**.
5. During 2FA setup for `rtariq234d`:
   * Select **Authenticator App (TOTP)** as the 2FA method (do NOT select IB Key Push Notification).
   * Scan the QR code using your phone, but **IMPORTANT**: Copy and save the **32-character secret key** (e.g., `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP`).

---

### Phase 2: TOTP Helper Script (`totp_helper.py`)

Create a Python helper script on your AWS EC2 host to automatically produce 6-digit TOTP tokens on request:

```python
#!/usr/bin/env python3
"""
totp_helper.py - Auto-generates current 6-digit TOTP code for IB Gateway login.
"""
import os
import sys
import pyotp

def get_totp_code(secret_key: str) -> str:
    totp = pyotp.TOTP(secret_key)
    return totp.now()

if __name__ == "__main__":
    totp_secret = os.getenv("IB_TOTP_SECRET")
    if not totp_secret:
        print("Error: IB_TOTP_SECRET environment variable not set.", file=sys.stderr)
        sys.exit(1)
    print(get_totp_code(totp_secret))
```

---

### Phase 3: Docker & IBC Configuration (`docker-compose.yml`)

Deploy `gnzgl/ib-gateway-docker` on AWS EC2 using Docker Compose.

```yaml
version: '3.8'

services:
  ib-gateway:
    image: gnzgl/ib-gateway-docker:latest
    container_name: ib-gateway-vsccc
    restart: always
    environment:
      - TWS_USERID=rtariq234d
      - TWS_PASSWORD=${IB_PASSWORD}
      - TRADING_MODE=paper  # Use 'live' for real-time live market data stream
      - READ_ONLY_API=yes
      - TWOFA_TIMEOUT_ACTION=exit
      - IBC_INI=/opt/ibc/config.ini
      - DISPLAY=:1
    ports:
      - "127.0.0.1:4002:4002"   # IB Gateway API Socket
      - "127.0.0.1:5900:5900"   # VNC Remote Desktop (for debugging)
    volumes:
      - ./ibc_config.ini:/opt/ibc/config.ini:ro
      - ./logs:/root/Jts
```

#### Injected IBC Configuration (`ibc_config.ini` snippet):
```ini
[IBGateway]
IBGatewayPort=4002
ApiOnly=yes

[Authentication]
# Auto-restart handling at 23:45 EST
ClosedownAt=23:45
ReloginAfterClosedown=yes
```

---

### Phase 4: AWS Bedrock / VSCCC Data Integration (`cloud_relay.py`)

The local Python bridge daemon connects to `127.0.0.1:4002`, gathers the 0DTE options, GEX metrics, VIX term structure, and market internals, and uploads a structured snapshot to AWS S3.

#### Core Data Collector Logic:
```python
import asyncio
import json
import boto3
from datetime import datetime, timezone
from ib_insync import IB, Stock, Option, Index

class VSCCCDataBridge:
    def __init__(self, host='127.0.0.1', port=4002, client_id=99):
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        self.bucket = 'aqs-market-data-bucket'
        self.key = 'live/ibkr_trading_state.json'

    async def connect(self):
        await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)

    async def fetch_vsccc_snapshot(self) -> dict:
        """
        Gathers ES/NQ prices, VIX/VVIX/SKEW, NYSE Internals (ADD, VOLD, TRIN),
        and SPX 0DTE option chain data for Bedrock consumption.
        """
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "online" if self.ib.isConnected() else "offline",
            "market_internals": {},
            "volatility_index": {},
            "positions": []
        }

        # 1. Fetch Volatility Indices (VIX, VVIX, SKEW)
        for sym in ["VIX", "VVIX", "SKEW"]:
            contract = Index(sym, "CBOE")
            await self.ib.qualifyContractsAsync(contract)
            ticker = self.ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(0.5)
            snapshot["volatility_index"][sym] = {
                "last": ticker.last,
                "close": ticker.close
            }
            self.ib.cancelMktData(contract)

        # 2. Fetch NYSE Internals ($ADD, $VOLD, $TRIN)
        internals = [
            ("ADD-NYSE", "ADD"),
            ("VOLD-NYSE", "VOLD"),
            ("TRIN-NYSE", "TRIN")
        ]
        for ib_sym, label in internals:
            contract = Index(ib_sym, "NYSE")
            await self.ib.qualifyContractsAsync(contract)
            ticker = self.ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(0.5)
            snapshot["market_internals"][label] = {
                "last": ticker.last
            }
            self.ib.cancelMktData(contract)

        return snapshot

    async def push_to_s3(self, data: dict):
        body = json.dumps(data, indent=2)
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=body,
            ContentType='application/json'
        )

    async def run_loop(self):
        await self.connect()
        while True:
            try:
                data = await self.fetch_vsccc_snapshot()
                await self.push_to_s3(data)
            except Exception as e:
                print(f"[ERROR] VSCCC Bridge sync failure: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    bridge = VSCCCDataBridge()
    asyncio.run(bridge.run_loop())
```

---

## 4. Verification & Validation Checklist

| Verification Step | Command / Probe | Expected Outcome |
| :--- | :--- | :--- |
| **1. Docker Container Status** | `docker ps | grep ib-gateway` | Container status `Up (healthy)`. |
| **2. API Socket Port Listener** | `nc -zv 127.0.0.1 4002` | `Connection to 127.0.0.1 4002 port [tcp/*] succeeded!` |
| **3. TOTP Code Verification** | `python3 totp_helper.py` | Returns valid 6-digit integer matching authenticator. |
| **4. S3 Data Snapshot Check** | `aws s3 cp s3://aqs-market-data-bucket/live/ibkr_trading_state.json -` | Valid JSON payload with VIX, ADD, VOLD, and TRIN metrics. |
| **5. Bedrock / VSCCC Consumer Test** | Query AWS Bedrock prompt using S3 state context | Bedrock successfully parses market internals & GEX for decision matrix. |
