# GLOBAL GOVERNANCE: Atlas Quant AI Agent Operating Contract

This repository is the central Open Knowledge Format (OKF) Second Brain for Atlas Quant Systems (AQS). All AI agents (Google Antigravity, Claude Code, GitHub Copilot) operating within this vault or any connected workspace must strictly adhere to these 5 Non-Negotiable Pillars:

## PILLAR 1: P.A.R.A. & OPEN KNOWLEDGE FORMAT (OKF) DISCIPLINE
- All notes, research, and technical assets must be filed strictly under:
  * `1_Projects/` (Active initiatives with defined goals and completion criteria)
  * `2_Areas/` (Ongoing operational standards and maintenance domains)
  * `3_Resources/` (Knowledge hubs, mirrored architecture manuals, and reference materials)
  * `4_Archives/` (Completed, decommissioned, or inactive assets)
- **Directory Maps**: Every directory level must maintain an `index.md`. NEVER delete or overwrite `index.md` files; append or update them incrementally.
- **Link Integrity**: Preserve horizontal `[[WikiLinks]]` and relative path formatting across all notes.

## PILLAR 2: THE KARPATHY RSI LOOP & SYSTEMATIC VERIFICATION
- **Empirical Execution Cadence**: State Verifiable Claim -> Execute Smallest Discrete Check (<50 lines) -> Inspect Stdout/Trace/Log -> Classify PASS/FAIL -> Advance.
- **Pre-Flight Diff Declaration**: Before editing any code or configuration, explicitly state which files will be modified and which will NOT be touched.
- **Test-First & Compilation Guard**: For algorithmic or indicator modifications, verify against test suites or compiler boundaries with zero warnings before claiming completion.

## PILLAR 3: SOCRATIC ALIGNMENT & "GRILL-ME" SPARRING
- **No Yes-Machines**: Proactively challenge assumptions, probe edge cases, and expose potential failure modes before committing code or restructuring knowledge.
- **Clarification Budget**: Ask at most one tight, structured round of clarifying questions when requirements are underspecified; proceed with explicit assumptions rather than stalling.

## PILLAR 4: MULTIMODAL & BEDROCK KNOWLEDGE HARNESS
- **Rich Media & Visual Concepts**: When images, whiteboard sketches, or diagrams (`.png`, `.jpg`) are added to the vault, maintain companion description notes (e.g., `diagram.png.md`) capturing title, concept, and technical summary.
- **Multimodal Indexing**: Ensure rich media assets are indexed under dedicated `## Rich Media & Assets (Multimodal)` sections in their respective directory `index.md`.

## PILLAR 5: DOMAIN ISOLATION & INDICATOR INVARIANTS
- **Atlas.BullsBears RSI Boundary**: The 45–55 neutral zone, >65 bull regime, and <35 bear regime apply STRICTLY to `Atlas.BullsBears RSI`. These thresholds must NEVER be generalized to `Atlas.Trend`, `Atlas.Regime`, ADX, or general financial analysis.
- **Strict Domain Boundary**: Zone `vps_nt8` (NinjaTrader 8 C#, LevelBus, Renko bar mechanics, and sizing databases) has ZERO dependency on Zone `aws_cloud` (AWS Bedrock, CloudFront, S3, Cognito), and vice-versa. Never cite or cross-import AWS cloud documentation for NT8 C# logic.

---

## Prohibitions (Never Do)
- NEVER modify internal P.A.R.A folder names (`1_Projects`, `2_Areas`, `3_Resources`, `4_Archives`).
- NEVER delete or overwrite `index.md` files without incremental updating.
- NEVER perform state-altering or destructive actions without explicit operator confirmation.
