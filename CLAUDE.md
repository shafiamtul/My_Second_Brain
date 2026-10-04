# CLAUDE.md: AQS Second Brain Implementation Skills

## Core Operational Tenets
1. **Karpathy RSI Cadence**: Work in discrete changes of under 50 lines. State a verifiable claim, run a focused check, inspect results, and classify PASS or FAIL before advancing.
2. **Indicator Invariants**: The 45–55 neutral zone, >65 bull, and <35 bear thresholds belong STRICTLY to `Atlas.BullsBears RSI`. Do NOT generalize them to `Atlas.Trend`, `Atlas.Regime`, or general analysis.
3. **P.A.R.A Structure**: Maintain clean separation across `1_Projects/`, `2_Areas/`, `3_Resources/`, and `4_Archives/`. Never delete `index.md` files; append only.
4. **Socratic Alignment**: Proactively challenge assumptions, probe edge cases, and expose failure modes before modifying architecture or code.

## Verification & Automation Commands
- **Rebuild OKF Index**: `python3 indexer.py`
- **Rebuild Vector RAG**: `python3 vector_rag.py`
- **Query Second Brain RAG**: `python3 query_rag.py "{QUESTION}"`
- **Run Telemetry Logger**: `python3 vsc_logger.py --task "{NAME}" --status "{PASS|FAIL}" --log "{OUTPUT}"`

## Project Conventions
- **Naming**: Use camelCase for NT8 Indicators; snake_case for Python scripts.
- **Durable Facts**: If a new architectural or API fact is discovered, append it to `3_Resources/Tech_Specs/durable_facts.md`.
- **Memory Preservation**: At the end of every session, summarize current work in `MEMORY.md` to prevent context collapse.
