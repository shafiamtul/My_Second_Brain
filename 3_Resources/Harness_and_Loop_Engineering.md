# Harness & Loop Engineering Architecture

## 1. Executive Summary
In modern autonomous AI agent design and systematic trading systems, **the model is merely the probabilistic cognitive core; the harness is the deterministic structural scaffolding that enforces correctness, safety, and operational discipline.**

Harness and Loop Engineering represent the formal methodologies used within the **Atlas Quant Systems (AQS) Second Brain** to turn probabilistic Large Language Models (LLMs) into reliable, self-healing, and production-grade software engineers and trading analysts.

---

## 2. Harness Engineering Principles

```
┌────────────────────────────────────────────────────────┐
│                   DETERMINISTIC HARNESS                │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ Guardrails       │  │ Observation & Verification │  │
│  │ • Scope Limits   │  │ • Linting & Compilation    │  │
│  │ • Line Budgets   │  │ • Backtest Telemetry       │  │
│  │ • Stop Triggers  │  │ • Vector Integrity Checks  │  │
│  └────────┬─────────┘  └─────────────▲──────────────┘  │
│           │                          │                 │
│           ▼                          │                 │
│     ┌────────────────────────────────┴───────┐         │
│     │          PROBABILISTIC AGENT           │         │
│     │        (Claude / Nova / Bedrock)       │         │
│     └────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────┘
```

### Core Tenets:
1. **Separation of Cognition and Authority:** The agent proposes code, analysis, or trades; the harness controls file I/O, network execution, build checks, and deployment permissions.
2. **Deterministic Containment:** An LLM must never be allowed unconstrained filesystem or network access without predefined guardrails (e.g., sandbox policies, explicit pre-flight diff declarations, line-budget triggers).
3. **Fail-Fast Boundary Invariants:**
   * *Line-Budget Limit:* Any atomic modification approaching ~100 lines must trigger a hard pause and review to prevent overengineering.
   * *Pre-Flight Diff Declaration:* Exact files to be modified must be declared before edits begin. Any diff spilling into undeclared files halts execution immediately.
   * *Reversibility Requirement:* All harness actions must have deterministic rollback procedures.

---

## 3. Loop Engineering: The Karpathy Harness Loop

The Second Brain executes on a continuous, disciplined execution cycle adapted from the **Karpathy Harness Loop**:

```
           ┌─────────────────────────────┐
           │ 1. Observe & Plan           │
           │ (Read Context & Nearest Index│
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 2. Execute Small (<=50 lines│
           │ (Discrete, Atomic Mutation) │
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 3. Automated Verification   │
           │ (Typecheck / Test / Syntax) │
           └──────────────┬──────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
     [Checks Pass]              [Checks Fail]
              │                       │
              ▼                       ▼
┌───────────────────────────┐  ┌──────────────────────────┐
│ 4. Persist & Distill      │  │ Revert or Self-Heal Loop │
│ (Update Index / Facts)    │  │ (Max 3 retries -> Pause) │
└───────────────────────────┘  └──────────────────────────┘
```

### The 4 Phases of the Loop:
1. **Observation & Intent Mapping:** 
   * Agent reads the nearest `index.md`, durable facts (`durable_facts.md`), and active context before writing any code.
   * States explicit assumptions and produces a 3-line impact map.
2. **Atomic Execution:**
   * Strict adherence to baby steps: single logical changes under 50 lines. No speculative features, no unsolicited refactors.
3. **Automated Verification:**
   * The harness invokes immediate deterministic validation:
     * NinjaTrader / C#: Roslyn build or compiler checks.
     * Python / Quant: Pytest, AST parsing, or CPCV backtest assertions.
     * Web / Next.js: `tsc --noEmit` and static bundle verification.
4. **Distillation & Memory Preservation:**
   * Once validated, durable learnings are committed to memory (`MEMORY.md`) and indexes are updated to prevent context drift for future cycles.

---

## 4. Runaway Prevention & Circuit Breakers
To prevent infinite loops, hallucination drift, or token exhaustion:
* **Max Retry Cap:** Any command or build failing 3 consecutive times immediately fires a `STOP CONDITION TRIGGERED: Repeated Failure`.
* **State Checkpointing:** Every loop iteration records its state to disk so crashes or server restarts can resume without re-running expensive steps.

---

## Horizontal Connections
* [[3_Resources/Context_Engineering]] *(Active context window management for harness loops)*
* [[3_Resources/Multi_Modal_RAG_and_Vector_DB]] *(Retrieval grounding for agent observation phases)*
* [[AGENTS.md]] *(Vault operational governance rules)*
