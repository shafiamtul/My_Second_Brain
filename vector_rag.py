import os
import json
import time
from pathlib import Path
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Embeddings model config
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
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
        print(f"❌ Failed to get embedding for text: {e}")
        return None

def chunk_markdown(text: str, max_chars: int = 1200, overlap: int = 150) -> list:
    # Basic paragraph/header-aware chunking
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_len = len(line) + 1
        if current_length + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            # Keep overlap lines
            overlap_lines = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
            current_chunk = list(overlap_lines)
            current_length = sum(len(l) + 1 for l in current_chunk)
            
        current_chunk.append(line)
        current_length += line_len
        
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def chunk_code(text: str, max_lines: int = 60, overlap_lines: int = 10) -> list:
    # Code-aware chunking (line-based)
    lines = text.split("\n")
    chunks = []
    
    i = 0
    while i < len(lines):
        chunk_lines = lines[i : i + max_lines]
        chunks.append("\n".join(chunk_lines))
        i += max_lines - overlap_lines
        if i >= len(lines):
            break
            
    return chunks

def should_exclude(path: Path) -> bool:
    exclusions = ["node_modules", ".venv", ".git", ".next", "__pycache__", ".DS_Store", "build", "dist", ".brain"]
    parts = path.parts
    # Exclude hidden files or directories
    for part in parts:
        if part.startswith(".") and part != ".":
            return True
        if part in exclusions:
            return True
    return False

def scan_roots(obsidian_root: Path, trading_root: Path):
    allowed_extensions = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".json", ".yml", ".yaml"}
    scanned_files = {}
    
    # 1. Scan Obsidian root
    for p in obsidian_root.glob("**/*"):
        if p.is_file() and p.suffix.lower() in allowed_extensions and not should_exclude(p):
            scanned_files[str(p.resolve())] = p.stat().st_mtime
            
    # 2. Scan Trading root
    for p in trading_root.glob("**/*"):
        if p.is_file() and p.suffix.lower() in allowed_extensions and not should_exclude(p):
            scanned_files[str(p.resolve())] = p.stat().st_mtime
            
    return scanned_files

def main():
    obsidian_root = Path(__file__).parent.resolve()
    trading_root = Path("/Users/tariqrasheeduddin/Documents/Trading")
    
    print("🧠 Initializing Unified Vector RAG Database...")
    print(f"Scanning notes in: {obsidian_root}")
    print(f"Scanning codebase in: {trading_root}")
    
    # 1. Scan current files on disk
    scanned_files = scan_roots(obsidian_root, trading_root)
    print(f"Found {len(scanned_files)} eligible files for indexing.")
    
    # 2. Load existing vector store
    db = {}
    if VECTOR_STORE_PATH.exists():
        try:
            with open(VECTOR_STORE_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
            print(f"Loaded existing index containing {len(db)} files.")
        except Exception as e:
            print(f"Warning: Failed to load existing database, starting fresh. {e}")
            
    client = get_bedrock_client()
    if not client:
        print("❌ Cannot proceed: AWS Bedrock client unavailable.")
        return
        
    db_updated = False
    
    # 3. Clean up deleted files from db
    deleted_files = [f for f in db if f not in scanned_files]
    if deleted_files:
        for f in deleted_files:
            print(f"🗑️ Removing deleted file from index: {Path(f).name}")
            del db[f]
        db_updated = True
        
    # 4. Ingest new or modified files
    processed_count = 0
    embedded_chunks_count = 0
    
    for filepath_str, mtime in scanned_files.items():
        filepath = Path(filepath_str)
        
        # Incremental check
        if filepath_str in db and db[filepath_str].get("mtime") == mtime:
            continue
            
        print(f"⚙️ Processing/Embedding file: {filepath.name} ...")
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as err:
            print(f"❌ Failed to read {filepath.name}: {err}")
            continue
            
        ext = filepath.suffix.lower()
        
        # Segment/Chunk based on file type
        if ext in [".md", ".txt"]:
            chunks = chunk_markdown(content)
        elif ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".sh"]:
            chunks = chunk_code(content)
        else: # yml, json, yaml
            chunks = chunk_markdown(content, max_chars=800) # Smaller chunks for structured data
            
        file_chunks_data = []
        for idx, text_chunk in enumerate(chunks):
            # Skip empty chunks
            if not text_chunk.strip():
                continue
                
            # Get Bedrock Titan Vector embedding
            vector = get_titan_embedding(client, text_chunk)
            if vector:
                file_chunks_data.append({
                    "chunk_index": idx,
                    "text": text_chunk,
                    "embedding": vector
                })
                embedded_chunks_count += 1
                # Small rate-limit protection sleep
                time.sleep(0.1)
                
        db[filepath_str] = {
            "mtime": mtime,
            "filename": filepath.name,
            "chunks": file_chunks_data
        }
        db_updated = True
        processed_count += 1
        
    # 5. Save database
    if db_updated:
        VECTOR_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(VECTOR_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(db, f)
            print("💾 Vector database saved successfully.")
        except Exception as e:
            print(f"❌ Failed to save vector database: {e}")
            
    print(f"Process complete. Embedded {processed_count} files ({embedded_chunks_count} chunks). Total indexed files in DB: {len(db)}")

if __name__ == "__main__":
    main()
