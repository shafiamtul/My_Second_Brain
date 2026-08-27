import os
import sys
import json
import math
from pathlib import Path
import boto3

# Configuration
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
LLM_MODEL_ID = "amazon.nova-pro-v1:0"
VECTOR_STORE_PATH = Path(__file__).parent.resolve() / ".brain" / "vector_store.json"

def get_bedrock_client():
    try:
        session = boto3.Session(profile_name="aqs-automation")
        return session.client("bedrock-runtime", region_name="us-east-1")
    except Exception as e:
        print(f"Error creating Bedrock client: {e}")
        return None

def get_titan_embedding(client, text: str):
    payload = {
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    }
    try:
        response = client.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response["body"].read().decode("utf-8"))
        return response_body.get("embedding")
    except Exception as e:
        print(f"❌ Failed to get embedding for query: {e}")
        return None

def dot_product(v1, v2):
    return sum(a * b for a, b in zip(v1, v2))

def search_database(query_vector, db, top_k=6):
    results = []
    
    for filepath, data in db.items():
        for chunk in data.get("chunks", []):
            vector = chunk.get("embedding")
            if not vector:
                continue
                
            similarity = dot_product(query_vector, vector)
            results.append({
                "filepath": filepath,
                "filename": data["filename"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "similarity": similarity
            })
            
    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

def synthesize_answer(client, query: str, context_chunks: list):
    # Construct context block
    context_str = ""
    for idx, chunk in enumerate(context_chunks):
        context_str += f"--- SOURCE {idx+1}: {chunk['filepath']} (Similarity: {chunk['similarity']:.3f}) ---\n"
        context_str += f"{chunk['text']}\n\n"
        
    system_prompt = (
        "You are the master executive AI assistant for Atlas Quant Systems (AQS). "
        "You have access to the user's Second Brain notes and active code repositories. "
        "Using the provided retrieved context sources, synthesize a clear, comprehensive, and accurate answer to the user's query.\n"
        "Rules:\n"
        "1. Prioritize code structures and specific documentation retrieved in the sources.\n"
        "2. Provide direct markdown links to the sources using the file:// scheme (e.g. [schwab_client.py](file:///path/to/schwab_client.py)).\n"
        "3. If the answer is not in the context, explicitly state that you cannot find it in their current brain index.\n"
        "4. Be direct and technical. Keep standard chat summaries to a minimum."
    )
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": f"System Instructions:\n{system_prompt}\n\nContext:\n{context_str}\n\nQuery: {query}"
                    }
                ]
            }
        ]
    }
    
    try:
        response = client.invoke_model(
            modelId=LLM_MODEL_ID,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response["body"].read().decode("utf-8"))
        return response_body["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        return f"❌ Failed to synthesize answer with Bedrock Nova Pro: {e}"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 query_rag.py \"[Your question]\"")
        return
        
    query = " ".join(sys.argv[1:])
    
    if not VECTOR_STORE_PATH.exists():
        print(f"❌ Vector database not found at {VECTOR_STORE_PATH}. Please run vector_rag.py first.")
        return
        
    print("📂 Loading Vector Database...")
    try:
        with open(VECTOR_STORE_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read vector database: {e}")
        return
        
    client = get_bedrock_client()
    if not client:
        print("❌ Bedrock client unavailable.")
        return
        
    print(f"🔍 Embedding query: \"{query}\" ...")
    query_vector = get_titan_embedding(client, query)
    if not query_vector:
        return
        
    print("⚡ Searching vector space...")
    top_chunks = search_database(query_vector, db, top_k=6)
    
    if not top_chunks:
        print("🤷 No matching context found.")
        return
        
    print("\n--- Retrieved Context Sources ---")
    for idx, chunk in enumerate(top_chunks):
        print(f"[{idx+1}] {chunk['filename']} (Sim: {chunk['similarity']:.3f}) -> {chunk['filepath']}")
        
    print("\n🤖 Generating Synthesized Answer via Bedrock Nova Pro...\n")
    answer = synthesize_answer(client, query, top_chunks)
    print(answer)

if __name__ == "__main__":
    main()
