# CLAUDE.md: Trading Implementation Skills

## Verification Commands
- **Backtest**: `python scripts/backtester.py --indicator {NAME}`
- **Build OKF Index**: `python scripts/indexer.py`
- **Telemetry Log**: `python scripts/vsc_logger.py "{COMMAND}"`

## Project Conventions
- **Naming**: Use camelCase for NT8 Indicators; snake_case for Python scripts.
- **Durable Facts**: If a new trading fact is discovered (e.g., a specific API limit), immediately append it to `3_Resources/Tech_Specs/durable_facts.md`.
- **Memory Preservation**: At the end of every session, summarize current work in `MEMORY.md` to prevent "context collapse" for the next agent.
