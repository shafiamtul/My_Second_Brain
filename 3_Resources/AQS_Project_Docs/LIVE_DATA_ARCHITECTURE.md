# AQS IBKR Data Bridge - Architecture Overview

## You Don't Need OAuth - It's Already Running on EC2

The IBKR data collection is **already happening** on an EC2 instance via:
- **scheduler_engine.py** - Pulls data from IBKR Socket API (port 4002)
- **data_controllers.py** - Collects futures, options, GEX, breadth, news
- **db_relay.py** - Writes to Redis + DuckDB + DynamoDB

**Your FastAPI (this service) is a READ-ONLY relay** that serves this existing data.

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                   EC2 Instance (Headless)                 │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ scheduler_engine.py (runs 24/7)                      │  │
│  │ ├─ Connects to IBKR Socket (port 4002)              │  │
│  │ ├─ Dispatches data_controllers (futures, options)    │  │
│  │ ├─ Writes to Redis (cache)                           │  │
│  │ ├─ Writes to DuckDB (historical)                     │  │
│  │ └─ Pushes to DynamoDB (AWS backup)                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Local Services (Docker)                              │  │
│  │ ├─ Redis (on port 6379)  ← live cache               │  │
│  │ ├─ DuckDB (market_telemetry.db) ← time series       │  │
│  │ └─ Scheduler cron jobs (every 10-30s)               │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
              ▲
              │ Redis pub/sub
              │ DuckDB queries
              │
┌────────────────────────────────────────────────────────────┐
│              Your Machine (Localhost)                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ live_data_relay.py (reads from Redis/DuckDB)         │  │
│  │ ├─ Connects to remote Redis (EC2:6379)              │  │
│  │ ├─ Queries remote DuckDB                             │  │
│  │ └─ Caches recent snapshots locally                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                      ▲                                      │
│                      │ HTTP REST                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ FastAPI main.py (port 8000)                          │  │
│  │ ├─ GET /status            → health check            │  │
│  │ ├─ GET /account           → account summary         │  │
│  │ ├─ GET /positions         → portfolio               │  │
│  │ ├─ GET /market-data       → live quotes             │  │
│  │ ├─ GET /gex               → GEX levels              │  │
│  │ ├─ GET /breadth           → $ADD/$TICK/$TRIN        │  │
│  │ ├─ GET /api/history       → 24h compiled snapshot   │  │
│  │ └─ WebSocket /ws/ticks    → real-time stream        │  │
│  └──────────────────────────────────────────────────────┘  │
│                      ▲                                      │
│                      │ HTTP Fetch                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Next.js Dashboard (port 3000)                        │  │
│  │ ├─ GexStrikeMapPanel component                      │  │
│  │ ├─ Market data feeds                                 │  │
│  │ └─ Real-time ticker                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## How It Works

### 1. EC2 Scheduler (Always Running)
```python
# On EC2: scheduler_engine.py
while True:
    # Pull data from IBKR Socket
    futures = await fetch_futures()  # ES, NQ, YM, RTY, etc.
    gex = await fetch_gex()          # SPY/QQQ gamma exposure
    breadth = await fetch_breadth()  # $ADD, $TICK, $TRIN
    
    # Write to Redis (live)
    redis.set("aqs:live:FUTURES", json.dumps(futures))
    redis.set("aqs:live:GEX_LEVELS", json.dumps(gex))
    redis.set("aqs:live:BREADTH", json.dumps(breadth))
    
    # Write to DuckDB (history)
    duckdb.execute("INSERT INTO telemetry ...")
    
    # Publish to Redis pub/sub
    redis.publish("aqs:ticks:FUTURES", json.dumps(futures))
    
    await asyncio.sleep(10)  # RTH: 10s, ETH: 30s
```

### 2. Your FastAPI (Read-Only Relay)
```python
# Your machine: main.py
@app.get("/market-data")
async def get_market_data(symbols: str):
    # Read from live Redis cache
    quotes = relay.get_quotes(symbols.split(","))
    return {"quotes": quotes}

@app.get("/gex")
async def get_gex():
    # Read latest GEX snapshot from Redis
    gex = relay.get_gex_snapshot()
    return {"gex": gex}
```

### 3. Dashboard Fetches (Real-Time)
```javascript
// Next.js dashboard
useEffect(() => {
  const fetchData = async () => {
    // Fetch from local FastAPI
    const res = await fetch('http://localhost:8000/gex');
    const gex = await res.json();
    setGexData(gex);
  };
  fetchData();
}, []);
```

---

## Data Flow Summary

| Source | Collection | Storage | Your Service | Dashboard |
|--------|-----------|---------|--------------|-----------|
| **IBKR Socket** | `scheduler_engine.py` (EC2) | Redis + DuckDB | `live_data_relay.py` reads | `FastAPI` serves |
| **24h History** | `db_relay.py` writes | DuckDB | Queries for candles | Charts display |
| **Live Ticks** | Controllers push | Redis pub/sub | Subscribes | WebSocket stream |
| **GEX Levels** | Options controller | Redis cache | Snapshots every 30s | Real-time panel |

---

## Key Advantages

✅ **No New IBKR Connections** - Reuse existing EC2 scheduler  
✅ **Highly Available** - Redis + DuckDB = local redundancy  
✅ **History Preserved** - 24h at 30s intervals in DuckDB  
✅ **Real-Time** - WebSocket ticks to dashboard  
✅ **Scalable** - Can move FastAPI to AWS Lambda  
✅ **Headless** - EC2 scheduler runs 24/7, you don't manage it  

---

## Configuration

### Connect to EC2 Redis

Edit `.env`:
```bash
# If running locally against local Redis:
IB_BRIDGE_REDIS_HOST=127.0.0.1
IB_BRIDGE_REDIS_PORT=6379

# If connecting to remote EC2 Redis:
IB_BRIDGE_REDIS_HOST=<ec2-instance-ip>
IB_BRIDGE_REDIS_PORT=6379
```

Then update `config.py` to read:
```python
redis_host = os.getenv("IB_BRIDGE_REDIS_HOST", "127.0.0.1")
redis_port = int(os.getenv("IB_BRIDGE_REDIS_PORT", 6379))
```

---

## Endpoints

### Status & Health
- `GET /status` - Check Redis/DuckDB health

### Account & Portfolio
- `GET /account` - Account summary from Redis
- `GET /positions` - Portfolio positions from Redis

### Market Data
- `GET /market-data?symbols=ES,NQ,SPY` - Live quotes
- `GET /gex` - GEX levels for SPY/QQQ
- `GET /breadth` - Market breadth ($ADD, $TICK, $TRIN)

### History & Real-Time
- `GET /api/history` - Latest 24h snapshot
- `WebSocket /ws/ticks` - Real-time tick stream

---

## Troubleshooting

### "Redis connection refused"
- Check EC2 Redis is running and reachable
- Verify network firewall allows port 6379
- Test: `redis-cli -h <ec2-ip> ping`

### "DuckDB read-only error"
- Ensure DuckDB file has read permissions
- Check `market_telemetry.db` exists on EC2

### "No data in /gex endpoint"
- Check scheduler_engine.py is running on EC2
- Verify Redis keys exist: `redis-cli KEYS "aqs:*"`

---

## Next Steps

1. **Verify EC2 Scheduler Running**
   ```bash
   ssh ec2-user@<instance>
   ps aux | grep scheduler_engine
   ```

2. **Test Redis Connection**
   ```bash
   redis-cli -h <ec2-ip> GET "aqs:live:FUTURES"
   ```

3. **Start FastAPI**
   ```bash
   python main.py
   ```

4. **Wire Dashboard**
   - Update `public-site/src/app/dashboard/page.tsx`
   - Replace mock data with fetches from `http://localhost:8000/*`

5. **Deploy to Production**
   - Move FastAPI to AWS Lambda
   - CloudFront + API Gateway frontend
   - DynamoDB backup replicas

---

**No OAuth setup needed. The data is already flowing from EC2 to your local machine.**
