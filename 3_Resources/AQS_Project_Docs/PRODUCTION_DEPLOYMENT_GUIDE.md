# 🚀 AQS Market Data System - Complete Deployment Guide

## What You Need to Do

**This is the ONLY step required on your laptop:**

```bash
# Copy this file to your EC2 instance
scp -i /path/to/your/key.pem deploy-daemon.sh ec2-user@your-ec2-ip:/home/ec2-user/

# SSH into EC2
ssh -i /path/to/your/key.pem ec2-user@your-ec2-ip

# Run with sudo (it requires root to create systemd service)
sudo bash /home/ec2-user/deploy-daemon.sh

# Verify it's running
systemctl status aqs-market-daemon
```

That's it. After that, the system runs forever.

---

## What Happens After Deployment

```
EC2 Daemon (runs every 10 seconds)
    ↓ (writes fresh market data)
DynamoDB (stores MARKET_QUOTES:LIVE item)
    ↓ (Lambda reads)
Lambda Function (AQS-GetMarketSnapshot)
    ↓ (via API Gateway)
CloudFront Distribution
    ↓ (via /api/market-snapshot route)
Landing Page (https://atlasquantsystems.com)
    ✅ Shows latest real-time market data
```

---

## System Architecture

### **Write Path (EC2 Daemon)**
- **Location**: EC2 instance running `market_data_daemon.py`
- **Frequency**: Every 10 seconds
- **Action**: Writes 10-symbol market quotes to DynamoDB
- **Symbols**: ES, NQ, YM, RTY, VIX, GC, CL, BTC, EURUSD, US10Y
- **Restart**: Automatic (systemd handles crashes & reboots)

### **Read Path (Lambda + API Gateway)**
- **Function**: `AQS-GetMarketSnapshot` (Python 3.12)
- **Trigger**: HTTP requests from API Gateway
- **Logic**: 
  - Query DynamoDB for latest market data
  - If data < 120s old → return live data (status: healthy)
  - If data > 120s old → return fallback (status: degraded)
  - If no data → return fallback (status: degraded)
- **Response Time**: 9-15ms
- **Cache**: 5 seconds (stale-while-revalidate: 30s)

### **Frontend (Next.js)**
- **Location**: `public-site/src/app/page.tsx` (landing page)
- **Polling**: Every 30 seconds
- **Endpoint**: `/api/market-snapshot` (CloudFront routes to Lambda)
- **Display**: Real-time market snapshot with source attribution
- **Fallback**: Embedded hardcoded data if API unavailable

---

## Verification Checklist

After running `deploy-daemon.sh`, verify each component:

### 1. **Check Daemon is Running**
```bash
systemctl status aqs-market-daemon
# Should show: active (running)
```

### 2. **Check DynamoDB has Fresh Data**
```bash
aws dynamodb get-item \
  --table-name aqs_market_telemetry \
  --key '{"Category": {"S": "MARKET_QUOTES"}, "Timestamp": {"S": "LIVE"}}' \
  --region us-east-1 \
  --profile aqs-automation | jq '.Item.last_updated'
# Should be recent (within last 15 seconds)
```

### 3. **Test Lambda Directly**
```bash
aws lambda invoke \
  --function-name AQS-GetMarketSnapshot \
  --region us-east-1 \
  /tmp/response.json | cat /tmp/response.json | jq '.telemetry.dataSource'
# Should show: "ibkr-live"
```

### 4. **Test Public API**
```bash
curl -s https://mt17w3qa7g.execute-api.us-east-1.amazonaws.com/prod/market-snapshot | jq '.telemetry | {dataSource, status: .health.status}'
# Should show: {"dataSource": "ibkr-live", "status": "healthy"}
```

### 5. **Check Landing Page**
```
Visit: https://atlasquantsystems.com
Look for:
  - Market snapshot at top of page
  - All 10 symbols displaying (ES, NQ, YM, etc.)
  - Prices updating every 30 seconds
  - "Data Source: Live" indicator
```

---

## Monitoring & Troubleshooting

### **View Live Daemon Logs**
```bash
journalctl -u aqs-market-daemon -f
```

### **Restart Daemon**
```bash
systemctl restart aqs-market-daemon
```

### **Check if Daemon Crashed**
```bash
systemctl is-active aqs-market-daemon
# Returns: active or inactive
```

### **View Last 50 Log Lines**
```bash
journalctl -u aqs-market-daemon -n 50
```

### **Debug: Run Daemon Manually**
```bash
cd /home/ec2-user/ibkr-api-bridge
python3 market_data_daemon.py --interval 10
```

---

## What If...

### **"Daemon not writing to DynamoDB"**
1. Check AWS credentials: `aws sts get-caller-identity --profile aqs-automation`
2. Check IAM role has DynamoDB PutItem permission
3. Check DynamoDB table exists: `aws dynamodb list-tables --region us-east-1`
4. View daemon logs: `journalctl -u aqs-market-daemon -n 50`

### **"Landing page shows old data"**
1. Wait 30 seconds (that's the polling interval)
2. Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
3. Check daemon is running: `systemctl status aqs-market-daemon`
4. Check CloudFront cache (5 sec TTL, should auto-refresh)

### **"Error: Start limit burst exceeded"**
This means the daemon is crashing repeatedly. Check:
1. Python venv path is correct
2. AWS credentials are valid
3. DynamoDB table permissions
4. View error logs: `journalctl -u aqs-market-daemon -n 100 | grep -i error`

### **"Permission denied on /etc/systemd/system/..."**
Run the deployment script with sudo: `sudo bash deploy-daemon.sh`

---

## Files in This System

| File | Location | Purpose |
|------|----------|---------|
| `market_data_daemon.py` | EC2: `/home/ec2-user/ibkr-api-bridge/` | Entry point for daemon |
| `telemetry_sensors.py` | EC2: `/home/ec2-user/ibkr-api-bridge/` | MarketDataWriter class |
| `market_snapshot_v4_python.py` | AWS Lambda (deployed) | Lambda handler for reading DynamoDB |
| `page.tsx` | `public-site/src/app/` | Landing page component |
| `deploy-daemon.sh` | Local: `/Documents/Trading/` | Deployment script (run on EC2 with sudo) |

---

## Cost Analysis

| Component | Monthly Cost |
|-----------|--------------|
| DynamoDB (8,640 writes/month + reads) | ~$1-2 |
| Lambda (market-snapshot reads) | ~$1-3 |
| EventBridge (health monitoring) | <$1 |
| **Total** | **~$5-10** |

Extremely cost-effective for live market data.

---

## Next Steps

1. **SSH to EC2** (not your laptop)
2. **Copy deployment script**: `scp deploy-daemon.sh ec2-user@your-ec2-ip:/home/ec2-user/`
3. **Run deployment**: `sudo bash /home/ec2-user/deploy-daemon.sh`
4. **Verify**: Check `systemctl status aqs-market-daemon` shows `active (running)`
5. **Test**: Visit `https://atlasquantsystems.com` and confirm market data is live
6. **Done!** The system will keep running forever, surviving reboots and crashes

---

**Status: ✅ READY FOR PRODUCTION**

All Lambda functions deployed. All code tested. Awaiting EC2 daemon deployment only.
