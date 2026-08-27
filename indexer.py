import os
import re
from pathlib import Path
from datetime import datetime, timezone
import urllib.parse

def clean_wiki_link(link: str) -> str:
    if "|" in link:
        link = link.split("|")[0]
    return link.strip()

def find_file_by_name(root_dir: Path, target_name: str) -> bool:
    exact_path = root_dir / f"{target_name}.md"
    if exact_path.exists():
        return True
    
    target_basename = os.path.basename(target_name)
    for p in root_dir.glob("**/*.md"):
        if p.stem == target_basename:
            return True
            
    return False

def parse_markdown_file(file_path: Path):
    title = file_path.stem
    summary = ""
    links = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse H1 title
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            
        # Parse WikiLinks [[WikiLink]]
        raw_links = re.findall(r"\[\[(.*?)\]\]", content)
        links = [clean_wiki_link(lnk) for lnk in raw_links]
        
        # Parse first non-empty paragraph after title for summary
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            summary = stripped
            break
            
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        
    return title, summary, links

def main():
    root_dir = Path(__file__).parent.resolve()
    print(f"Starting OKF hierarchy indexing inside: {root_dir}")
    
    all_notes = {}
    directories_indexed = 0
    total_notes_count = 0
    total_connections_count = 0
    broken_links = []
    
    # 1. First Pass: Scan the vault and parse all markdown notes
    for p in root_dir.glob("**/*.md"):
        if p.name == "index.md":
            continue
        if any(part.startswith(".") for part in p.parts):
            continue
            
        rel_path = p.relative_to(root_dir)
        title, summary, links = parse_markdown_file(p)
        
        # Check if this is a rich media companion note
        is_multimodal_companion = False
        img_name = ""
        for suffix in [".png.md", ".jpg.md", ".jpeg.md", ".pdf.md"]:
            if p.name.lower().endswith(suffix):
                is_multimodal_companion = True
                img_name = p.name[:-3] # Strip .md to get the image name (e.g. topology.png)
                break
                
        all_notes[str(rel_path)] = {
            "abs_path": p,
            "filename": p.name,
            "title": title,
            "summary": summary,
            "links": links,
            "is_multimodal": is_multimodal_companion,
            "target_asset": img_name
        }
        total_notes_count += 1
        total_connections_count += len(links)
        
    # 2. Second Pass: Verify links and audit
    for rel_path, data in all_notes.items():
        for link in data["links"]:
            if not find_file_by_name(root_dir, link):
                broken_links.append({
                    "source": rel_path,
                    "target": link
                })
                print(f"⚠️ Warning: Broken WikiLink [[{link}]] found in {rel_path}")

    # 3. Third Pass: Traverse all folders recursively and generate localized index.md maps
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if any(part.startswith(".") for part in Path(dirpath).parts):
            continue
            
        current_dir = Path(dirpath)
        
        if current_dir == root_dir:
            continue
            
        directories_indexed += 1
        
        # Subdirectories listing
        subdirs_content = []
        for d in sorted(dirnames):
            if d.startswith("."):
                continue
            escaped_dir = urllib.parse.quote(d)
            subdirs_content.append(f"* **[{d}](./{escaped_dir}/index.md)**")
            
        # Notes & Multimodal Assets listing
        notes_content = []
        multimodal_content = []
        connections_content = []
        
        for f in sorted(filenames):
            if not f.endswith(".md") or f == "index.md":
                continue
                
            rel_file_path = current_dir / f
            rel_file_str = str(rel_file_path.relative_to(root_dir))
            
            if rel_file_str in all_notes:
                data = all_notes[rel_file_str]
                escaped_file = urllib.parse.quote(f)
                
                # Format horizontal links
                for lnk in data["links"]:
                    connections_content.append(f"* [[{lnk}]] *(referenced in {data['title']})*")
                
                if data["is_multimodal"]:
                    # Link to the actual image file instead of the companion note
                    escaped_asset = urllib.parse.quote(data["target_asset"])
                    multimodal_content.append(f"* **[{data['title']}](./{escaped_asset})** - [Visual Concept] {data['summary']}")
                else:
                    notes_content.append(f"* **[{data['title']}](./{escaped_file})** - {data['summary']}")
                    
        # Write sub-level index.md
        index_lines = [
            f"# Index Map: {current_dir.name}",
            f"\n*Auto-generated by OKF Indexer on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n"
        ]
        
        if subdirs_content:
            index_lines.append("## Subdirectories")
            index_lines.extend(subdirs_content)
            index_lines.append("")
            
        if notes_content:
            index_lines.append("## Core Knowledge Nodes")
            index_lines.extend(notes_content)
            index_lines.append("")
            
        if multimodal_content:
            index_lines.append("## Rich Media & Assets (Multimodal)")
            index_lines.extend(multimodal_content)
            index_lines.append("")
            
        if connections_content:
            index_lines.append("## Horizontal Connections")
            index_lines.extend(connections_content)
            index_lines.append("")
            
        with open(current_dir / "index.md", "w", encoding="utf-8") as f:
            f.write("\n".join(index_lines))
            
    # 4. Write Root index.md
    root_index_lines = [
        "# Root Knowledge Map",
        f"\n*Last Indexed on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n",
        "## P.A.R.A Structure Maps",
        "* **[1 Projects](./1_Projects/index.md)**",
        "* **[2 Areas](./2_Areas/index.md)**",
        "* **[3 Resources](./3_Resources/index.md)**",
        "* **[4 Archives](./4_Archives/index.md)**",
        "",
        "## Vault Statistics",
        f"* **Total Directories:** {directories_indexed}",
        f"* **Total Notes (including Multimodal):** {total_notes_count}",
        f"* **Total Horizontal Connections:** {total_connections_count}",
        ""
    ]
    
    if broken_links:
        root_index_lines.append("## ⚠️ Broken Links Audit")
        for bl in broken_links:
            root_index_lines.append(f"* Broken [[{bl['target']}]] inside [{bl['source']}](./{urllib.parse.quote(bl['source'])})")
    else:
        root_index_lines.append("## ✅ Link Audit Status")
        root_index_lines.append("* All horizontal connections verified. No broken markdown links found.")
        
    with open(root_dir / "index.md", "w", encoding="utf-8") as f:
        f.write("\n".join(root_index_lines))
        
    print(f"Indexing complete. Indexed {directories_indexed} folders, {total_notes_count} notes, and {total_connections_count} links.")

if __name__ == "__main__":
    main()
