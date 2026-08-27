import os
import time
import subprocess
import base64
import json
from pathlib import Path
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Bedrock Nova Pro configuration
BEDROCK_MODEL_ID = "amazon.nova-pro-v1:0"

def get_bedrock_client():
    try:
        session = boto3.Session(profile_name="aqs-automation")
        return session.client("bedrock-runtime", region_name="us-east-1")
    except Exception as e:
        print(f"Error creating Bedrock client: {e}")
        return None

def describe_image_with_bedrock(image_path: Path) -> str:
    print(f"🔮 Sending image {image_path.name} to AWS Bedrock Nova Pro for analysis...")
    client = get_bedrock_client()
    if not client:
        return f"# {image_path.name}\n\n*Error: Bedrock client unavailable.*"
        
    try:
        # 1. Read and base64 encode image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            
        ext = image_path.suffix.lower().replace(".", "")
        if ext not in ["png", "jpeg", "jpg"]:
            ext = "png"
        if ext == "jpg":
            ext = "jpeg"
            
        # 2. Construct Nova payload
        prompt_text = (
            "Provide a clean markdown file describing this image for an Obsidian Second Brain vault.\n"
            "1. Include a short, descriptive title starting with a single H1 header (e.g. # Whiteboard Topology Sketch).\n"
            "2. Write a one-sentence conceptual summary directly below the title (marked as an italicized blockquote or paragraph).\n"
            "3. Provide a brief description of the key visual components, text labels, structures, and systems depicted (2-3 sentences).\n"
            "Output ONLY the clean markdown content. Do not include any standard conversational assistant intro or outro prose."
        )
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": ext,
                                "source": {
                                    "bytes": image_data
                                }
                            }
                        },
                        {
                            "text": prompt_text
                        }
                    ]
                }
            ]
        }
        
        # 3. Invoke Bedrock Model
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response["body"].read().decode("utf-8"))
        raw_text = response_body["output"]["message"]["content"][0]["text"]
        return raw_text.strip()
        
    except Exception as e:
        print(f"❌ AWS Bedrock invocation failed for {image_path.name}: {e}")
        return f"# {image_path.name}\n\n*Error: Failed to generate multimodal description. {e}*"

def scan_vault_files(root_dir: Path):
    notes = {}
    images = {}
    target_dirs = ["1_Projects", "2_Areas", "3_Resources"]
    
    image_extensions = [".png", ".jpg", ".jpeg"]
    
    for target in target_dirs:
        dir_path = root_dir / target
        if not dir_path.exists():
            continue
            
        for p in dir_path.glob("**/*"):
            if any(part.startswith(".") for part in p.parts):
                continue
                
            if p.is_file():
                ext = p.suffix.lower()
                if ext == ".md":
                    if p.name == "index.md":
                        continue
                    try:
                        notes[str(p)] = p.stat().st_mtime
                    except Exception:
                        pass
                elif ext in image_extensions:
                    try:
                        images[str(p)] = p.stat().st_mtime
                    except Exception:
                        pass
                        
    return notes, images

def scan_trading_files(trading_root: Path):
    allowed_extensions = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".json", ".yml", ".yaml"}
    mtimes = {}
    
    for dirpath, dirnames, filenames in os.walk(trading_root):
        # Modify dirnames in place to prevent entering excluded folders
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ["node_modules", ".venv", ".git", ".next", "__pycache__", "build", "dist", ".brain"]]
        
        for f in filenames:
            if f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in allowed_extensions:
                p = Path(dirpath) / f
                try:
                    mtimes[str(p)] = p.stat().st_mtime
                except Exception:
                    pass
    return mtimes

def check_and_mirror_docs(root_dir: Path) -> bool:
    import shutil
    
    dest_dir = root_dir / "3_Resources" / "AQS_Project_Docs"
    
    mappings = {
        "/Users/tariqrasheeduddin/Documents/Trading/ibkr-api-bridge/LIVE_DATA_ARCHITECTURE.md": "LIVE_DATA_ARCHITECTURE.md",
        "/Users/tariqrasheeduddin/Documents/Trading/ibkr-api-bridge/PLAYBOOK.md": "PLAYBOOK.md",
        "/Users/tariqrasheeduddin/Documents/Trading/ibkr-api-bridge/README.md": "IBKR_API_BRIDGE_README.md",
        "/Users/tariqrasheeduddin/Documents/Trading/PRODUCTION_DEPLOYMENT_GUIDE.md": "PRODUCTION_DEPLOYMENT_GUIDE.md",
        "/Users/tariqrasheeduddin/Documents/Trading/LAMBDA_DEPLOYMENT_GUIDE.md": "LAMBDA_DEPLOYMENT_GUIDE.md",
        "/Users/tariqrasheeduddin/Documents/Trading/DYNAMODB_INTEGRATION_GUIDE.md": "DYNAMODB_INTEGRATION_GUIDE.md",
        "/Users/tariqrasheeduddin/Documents/Trading/IBKR_DECOMMISSIONING_PLAN.md": "IBKR_DECOMMISSIONING_PLAN.md",
        "/Users/tariqrasheeduddin/Documents/Trading/IBKR_VS_SCHWAB_AUDIT.md": "IBKR_VS_SCHWAB_AUDIT.md",
        "/Users/tariqrasheeduddin/Documents/Trading/DATA_PIPELINE_VERIFICATION.md": "DATA_PIPELINE_VERIFICATION.md",
        "/Users/tariqrasheeduddin/Documents/Trading/ARCHITECTURE_SCHWAB_ONLY.md": "ARCHITECTURE_SCHWAB_ONLY.md",
    }
    
    changed = False
    
    for src_str, dest_name in mappings.items():
        src_path = Path(src_str)
        if not src_path.exists():
            continue
            
        dest_path = dest_dir / dest_name
        
        needs_copy = False
        if not dest_path.exists():
            needs_copy = True
        else:
            try:
                if src_path.stat().st_mtime > dest_path.stat().st_mtime:
                    needs_copy = True
            except Exception:
                needs_copy = True
                
        if needs_copy:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                print(f"🔄 Mirrored doc updated: {dest_name} (synced from workspace)")
                changed = True
            except Exception as e:
                print(f"❌ Failed to mirror doc {dest_name}: {e}")
                
    return changed

def main():
    root_dir = Path(__file__).parent.resolve()
    trading_root = Path("/Users/tariqrasheeduddin/Documents/Trading")
    
    print(f"👁️ Starting Second Brain Multimodal Vector RAG file watcher on: {root_dir}")
    print(f"Monitoring notes & codebase in: {trading_root}")
    
    # Initial scan
    cached_notes, cached_images = scan_vault_files(root_dir)
    cached_trading = scan_trading_files(trading_root)
    
    indexer_path = root_dir / "indexer.py"
    vector_rag_path = root_dir / "vector_rag.py"
    
    try:
        while True:
            time.sleep(3)
            # 0. Mirror files from trading workspace
            mirror_changed = check_and_mirror_docs(root_dir)
            
            # Scan current states
            current_notes, current_images = scan_vault_files(root_dir)
            current_trading = scan_trading_files(trading_root)
            
            vault_changed = mirror_changed
            trading_changed = False
            
            # 1. Process Images first to generate companion description .md files
            for img_path_str, img_mtime in current_images.items():
                img_path = Path(img_path_str)
                companion_md_path = img_path.with_name(img_path.name + ".md")
                
                needs_description = False
                if not companion_md_path.exists():
                    print(f"🖼️ Detected new image asset: {img_path.name}")
                    needs_description = True
                else:
                    try:
                        companion_mtime = companion_md_path.stat().st_mtime
                        if img_mtime > companion_mtime:
                            print(f"🖼️ Detected updated image asset: {img_path.name}")
                            needs_description = True
                    except Exception:
                        needs_description = True
                        
                if needs_description:
                    description_md = describe_image_with_bedrock(img_path)
                    try:
                        with open(companion_md_path, "w", encoding="utf-8") as f:
                            f.write(description_md)
                        print(f"✅ Generated companion description note: {companion_md_path.name}")
                        vault_changed = True
                    except Exception as err:
                        print(f"❌ Failed to write companion note for {img_path.name}: {err}")
            
            # 2. Check for Note changes (including newly created companion description notes)
            # Additions or modifications
            for filepath, mtime in current_notes.items():
                if filepath not in cached_notes:
                    print(f"🆕 Note added: {Path(filepath).name}")
                    vault_changed = True
                elif mtime > cached_notes[filepath]:
                    print(f"📝 Note modified: {Path(filepath).name}")
                    vault_changed = True
                    
            # Deletions
            for filepath in cached_notes:
                if filepath not in current_notes:
                    print(f"🗑️ Note deleted: {Path(filepath).name}")
                    vault_changed = True
                    
            # 3. Check for Code changes in Trading Workspace
            for filepath, mtime in current_trading.items():
                if filepath not in cached_trading:
                    print(f"🆕 Code file added: {Path(filepath).name}")
                    trading_changed = True
                elif mtime > cached_trading[filepath]:
                    print(f"📝 Code file modified: {Path(filepath).name}")
                    trading_changed = True
                    
            for filepath in cached_trading:
                if filepath not in current_trading:
                    print(f"🗑️ Code file deleted: {Path(filepath).name}")
                    trading_changed = True
                    
            # 4. Trigger pipelines based on change states
            if vault_changed:
                print("⚡ Note changes detected. Re-running indexing pipeline...")
                try:
                    subprocess.run(["python3", str(indexer_path)], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"❌ Indexer failed: {e}")
                    
            if vault_changed or trading_changed:
                print("⚡ Code or Note changes detected. Updating Vector RAG database...")
                try:
                    subprocess.run(["python3", str(vector_rag_path)], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"❌ Vector RAG update failed: {e}")
                    
                # Re-sync caches
                cached_notes, cached_images = scan_vault_files(root_dir)
                cached_trading = scan_trading_files(trading_root)
            else:
                cached_notes = current_notes
                cached_images = current_images
                cached_trading = current_trading
                
    except KeyboardInterrupt:
        print("\nWatcher stopped cleanly.")

if __name__ == "__main__":
    main()
