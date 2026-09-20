# Context Engineering Architecture

## 1. Executive Summary
**Context Engineering is the discipline of architecting, budgeting, and preserving the active information state delivered into an AI model's attention window.** 

While *prompt engineering* focuses on natural language phrasing, *context engineering* treats the LLM context window as a dynamic, high-value, and finite working memory system. Within the **Atlas Quant Systems (AQS) Second Brain**, context engineering ensures that agents maintain razor-sharp operational grounding without experiencing **Context Collapse**, hallucination, or token budget blowout.

---

## 2. Context Window Budget Allocation

An unconstrained context window degrades model attention and increases latency. In AQS, the context window is strictly budgeted across 5 functional tiers:

```
┌────────────────────────────────────────────────────────┐
│  TIER 1: Immutable Identity & Governance (~15%)        │
│  • Mission, Stop Conditions, Behavioral Invariants     │
├────────────────────────────────────────────────────────┤
│  TIER 2: Dynamic Semantic Grounding (~25%)             │
│  • Vector RAG Chunks, Relevant Indexes, Code Skeletons │
├────────────────────────────────────────────────────────┤
│  TIER 3: Durable Memory & Project State (~15%)         │
│  • MEMORY.md, durable_facts.md, Active Task Goals      │
├────────────────────────────────────────────────────────┤
│  TIER 4: Tool Execution & Verification Scratchpad (~35%)│
│  • Command Outputs, AST trees, Diffs, Build Results    │
├────────────────────────────────────────────────────────┤
│  TIER 5: Agent Reasoning & Generation Headroom (~10%)  │
│  • Scratch thinking tokens, plan output, final response│
└────────────────────────────────────────────────────────┘
```

---

## 3. Defense Against Context Collapse

### What is Context Collapse?
Context Collapse occurs over multi-turn agent sessions when:
1. Irrelevant terminal outputs and intermediate debugging noise accumulate in the chat trajectory.
2. The attention mechanism diffuses across hundreds of obsolete lines, causing the model to forget earlier constraints or architectural decisions.
3. The model begins hallucinating nonexistent functions or repeating failed patterns.

### Mitigation Mechanisms:
* **Progressive Disclosure:** Agents never load entire 10,000-line codebases. They inspect directory trees (`list_dir`), find symbols (`grep_search`), and read only bounded slices (`view_file` with `StartLine`/`EndLine`).
* **Context Compaction & Checkpointing:** When conversation histories exceed token thresholds, the harness compresses the trajectory into an atomic checkpoint summary, clearing transient error outputs while preserving core accomplishments and next steps.
* **Externalized Long-Term Memory:** Instead of forcing the LLM to remember complex state across turns, memory is persisted to disk in standardized files:
  * `MEMORY.md`: High-level session progress and open blockers.
  * `3_Resources/Tech_Specs/durable_facts.md`: Discovered platform limits, API constraints, and deterministic truths.

---

## 4. Multi-Agent Context Contracts
In complex pipelines (such as the AQS Market Telemetry Swarm), different tasks require distinct context states. Context engineering enforces **Clean Handoff Contracts**:

```
[ HARVESTER AGENT ]
Context: Raw Schwab/CME API Ticks & Quotes
Output: Clean, Normalized Snapshot JSON (Minimal Context Footprint)
       ↓
[ GEX_MATH AGENT ]
Context: Normalized Options Strikes & Volatility Data
Output: Precise Gamma Flip Levels & Delta Ratios
       ↓
[ OVERSEER AGENT ]
Context: Coherence Verification Rules & Output Schema
Output: Final Published Brief & Discord Dispatch
```
Each sub-agent receives only the exact payload necessary to execute its role, completely eliminating context pollution across domain boundaries.

---

## Horizontal Connections
* [[3_Resources/Harness_and_Loop_Engineering]] *(Execution scaffolding utilizing engineered context)*
* [[3_Resources/Multi_Modal_RAG_and_Vector_DB]] *(Dynamic context retrieval via vector stores)*
* [[AGENTS.md]] *(Vault operational governance rules)*
