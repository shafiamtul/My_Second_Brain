# Multi-Modal RAG & Vector Database Architecture

## 1. Executive Summary
The **Atlas Quant Systems (AQS) Second Brain** operates an autonomous, multi-modal Retrieval-Augmented Generation (RAG) and Vector Database system. It bridges textual engineering specs, quantitative algorithms, and visual market telemetry (charts, order flow diagrams, and volume profiles) into a unified semantic query layer.

Powered by **AWS Bedrock (Amazon Titan Embeddings v2 & Amazon Nova Pro)**, this architecture allows autonomous agents to retrieve, synthesize, and reason over both text and images with sub-second latency.

---

## 2. Multi-Modal RAG Ingestion Pipeline (`watcher.py`)

Trading systems rely heavily on visual patterns (Renko charts, volume profile distributions, and system topology sketches). Standard RAG systems are blind to images. The AQS Second Brain solves this through **Dual-Representation Indexing**:

```
[ Visual Asset Added (.png / .jpg) ]
(e.g., atlas_chart_renko.png, VolumeProfile.png)
                       │
                       ▼
         ┌───────────────────────────┐
         │ watcher.py Ingestion Loop │
         │ (Base64 Encoding)         │
         └─────────────┬─────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │  AWS Bedrock: Nova Pro Model  │
       │   (amazon.nova-pro-v1:0)      │
       └───────────────┬───────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│  Automated Companion Note (.png.md)                    │
│  • Structural Title (H1)                               │
│  • One-sentence conceptual summary                     │
│  • Detailed component breakdown & visual mechanics     │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
         [ Vector Store Embeddings (.brain) ]
```

### Benefits of Dual-Representation:
1. **Full Text-to-Image Searchability:** An agent querying *"What is the Renko slope synchronization threshold?"* retrieves the companion note associated with `atlas_chart_renko.png`.
2. **Deterministic Context Injection:** Markdown descriptions can be directly fed into text-only LLMs without requiring expensive multimodal re-encoding on every query.

---

## 3. Vector Database Architecture (`vector_rag.py`)

The local vector database lives in `.brain/vector_store.json` and is indexed incrementally on every file mutation:

### A. Embedding Engine
* **Model:** `amazon.titan-embed-text-v2:0` via AWS Bedrock (`us-east-1`).
* **Vector Dimensions:** `1024` dimensions.
* **Normalization:** Enforced (`"normalize": True`), allowing dot-product calculations to directly equal cosine similarity.

### B. Header-Aware Semantic Chunking
Naive fixed-character chunking destroys markdown hierarchy. The AQS chunker (`chunk_markdown`):
* **Window Size:** `1,200 characters` (optimal for technical paragraphs and code snippets).
* **Overlap:** `150 characters` (maintains continuity across chunk boundaries).
* **Boundary Detection:** Splits along paragraph breaks (`\n\n`) and markdown headers (`#`, `##`, `###`), preventing logical fragmentation.

```json
{
  "filepath": "3_Resources/AQS_System_Architecture.md",
  "filename": "AQS_System_Architecture.md",
  "chunks": [
    {
      "chunk_index": 0,
      "text": "# AQS System Architecture Blueprint\n...",
      "char_count": 942,
      "embedding": [0.0241, -0.0152, 0.0891, "..."]
    }
  ]
}
```

---

## 4. Retrieval & Semantic Querying (`query_rag.py`)

When an agent or user queries the Second Brain (`python query_rag.py "Explain GEX calculation boundaries"`):

1. **Query Vectorization:** The query text is encoded into a 1024-dimensional normalized vector via Titan Embeddings v2.
2. **Normalized Dot-Product k-NN:**
   $$\text{Similarity}(v_1, v_2) = \sum_{i=1}^{1024} v_{1,i} \cdot v_{2,i}$$
3. **Dynamic Context Assembly:** The top-$k$ ($k=6$) chunks with the highest similarity scores are extracted and formatted into an injection payload for Amazon Nova Pro.
4. **Grounded Synthesis:** The synthesis prompt strictly instructs Nova Pro to cite sources (`[[filename]]`), state facts with precision, and avoid speculative hallucinations.

---

## Horizontal Connections
* [[3_Resources/Harness_and_Loop_Engineering]] *(Agent verification cycles guided by RAG)*
* [[3_Resources/Context_Engineering]] *(Context window budgeting for retrieved RAG chunks)*
* [[3_Resources/AQS_System_Architecture]] *(Core telemetry schema indexed in vector DB)*
