import json
import os
import sys
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def create_vault_structure(json_path, base_path="."):
    """
    Reads a JSON specification and generates an Obsidian-like vault structure 
    with improved handling for frontmatter, concurrency, and error logging.
    """
    # 1. Load the JSON file
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 2. Extract Obsidian config
    vault_name = data.get("obsidian_config", {}).get("vault_name", "MyZettelkastenVault")
    vault_path = os.path.join(base_path, vault_name)
    
    # 3. Create the vault folder if it doesn't exist
    if not os.path.exists(vault_path):
        try:
            os.makedirs(vault_path)
            logging.info(f"Created vault directory: {vault_path}")
        except OSError as e:
            logging.error(f"Error creating vault directory: {e}")
            return
    
    # 4. Create .obsidian config folder (optional)
    obsidian_config_path = os.path.join(vault_path, ".obsidian")
    if not os.path.exists(obsidian_config_path):
        try:
            os.makedirs(obsidian_config_path)
            logging.info(f"Created .obsidian config directory at: {obsidian_config_path}")
        except OSError as e:
            logging.error(f"Error creating .obsidian directory: {e}")
            return
    
    # Minimal config file
    config_content = {
        "plugin": data.get("obsidian_config", {}).get("plugins_enabled", []),
        "settings": data.get("obsidian_config", {}).get("settings", {})
    }
    try:
        with open(os.path.join(obsidian_config_path, "app.json"), "w", encoding="utf-8") as config_file:
            json.dump(config_content, config_file, indent=2)
    except OSError as e:
        logging.error(f"Error writing Obsidian config: {e}")
    
    # 5. Prepare global tags
    global_tags = data.get("global_tags", [])
    
    # 6. Create folders and notes concurrently
    folders = data.get("folders", [])
    
    # Optional concurrency (ThreadPoolExecutor)
    tasks = []
    with ThreadPoolExecutor(max_workers=4) as executor:  # Adjust max_workers as desired
        for folder_info in folders:
            folder_name = folder_info["folder_name"]
            folder_path = os.path.join(vault_path, folder_name)
            folder_type = folder_info.get("folder_type", "")
            
            # Submit folder creation
            tasks.append(executor.submit(create_folder, folder_path))
            
            # Submit note creation tasks
            notes = folder_info.get("notes", [])
            for note in notes:
                tasks.append(executor.submit(
                    create_markdown_note,
                    folder_path,
                    note,
                    global_tags,
                    folder_type
                ))
        
        # Collect results
        for future in as_completed(tasks):
            result = future.result()
            if result is not None:
                logging.info(result)
    
    # 7. Optional: Generate README/index per folder
    #    You could iterate again over 'folders' to create a simple index of notes in each directory.
    #    For brevity, we won't do that here, but see the function `create_folder_readme` as an example:
    # generate_folder_indexes(folders, vault_path)

    logging.info(f"Vault '{vault_name}' created at: {vault_path}")


def create_folder(folder_path):
    """Creates a folder if it doesn't exist."""
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            return f"Created folder: {folder_path}"
        except OSError as e:
            logging.error(f"Error creating folder '{folder_path}': {e}")
    return None


def create_markdown_note(folder_path, note_data, global_tags, folder_type):
    """
    Creates a markdown note file within the specified folder_path.
    Incorporates frontmatter, global tags, link text, and error handling.
    """
    filename = note_data.get("filename")
    if not filename:
        return f"Skipping note with no filename in {folder_path}"
    
    note_path = os.path.join(folder_path, filename)
    content = note_data.get("content", "")
    
    # Merge tags: note tags + global tags
    note_tags = note_data.get("tags", [])
    merged_tags = list(set(note_tags + global_tags))  # remove duplicates
    
    # Build YAML frontmatter
    frontmatter_data = note_data.get("frontmatter", {})
    created_at = note_data.get("created_at", "")
    modified_at = note_data.get("modified_at", "")
    priority = note_data.get("priority", "")
    status = note_data.get("status", "")
    
    # The folder_type might be used as a frontmatter field or just ignored.
    # We'll store it as well, if provided.
    fm_lines = ["---"]
    fm_lines.append(f"title: {note_data.get('title', '')}")
    if created_at:
        fm_lines.append(f"created_at: {created_at}")
    if modified_at:
        fm_lines.append(f"modified_at: {modified_at}")
    if priority:
        fm_lines.append(f"priority: {priority}")
    if status:
        fm_lines.append(f"status: {status}")
    
    # Include the user-provided frontmatter
    for k, v in frontmatter_data.items():
        fm_lines.append(f"{k}: {v}")
    
    # Add tags to frontmatter
    if merged_tags:
        fm_lines.append(f"tags: {merged_tags}")
    
    # Possibly add folder_type
    if folder_type:
        fm_lines.append(f"folder_type: {folder_type}")
    
    fm_lines.append("---\n")
    yaml_frontmatter = "\n".join(fm_lines)
    
    # Convert links array to wiki links if needed
    # We'll just trust that the user may have inserted them in content,
    # but let's also systematically add them if we want:
    # note_links = note_data.get("links", [])
    # For each link, we might replace or insert a section.
    # However, the user example content already includes the wiki links.
    # So we just keep that approach.
    
    final_note = yaml_frontmatter + content
    
    # Write the file
    try:
        with open(note_path, "w", encoding="utf-8") as md_file:
            md_file.write(final_note)
        return f"Created note: {note_path}"
    except OSError as e:
        logging.error(f"Error writing note '{note_path}': {e}")
        return None


def generate_folder_indexes(folders, vault_path):
    """
    Example function to generate a README.md or _Index.md in each folder listing its notes.
    """
    for folder_info in folders:
        folder_name = folder_info["folder_name"]
        folder_path = os.path.join(vault_path, folder_name)
        readme_path = os.path.join(folder_path, "README.md")
        
        lines = [f"# Index for {folder_name}\n"]
        notes = folder_info.get("notes", [])
        for note in notes:
            filename = note.get("filename", "")
            title = note.get("title", "")
            if filename:
                lines.append(f"- [[{filename} | {title}]]")
        
        try:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logging.info(f"Created index at {readme_path}")
        except OSError as e:
            logging.error(f"Error writing index for folder '{folder_path}': {e}")


if __name__ == "__main__":
    # Usage:
    #   python generate_obsidian_improved.py /path/to/json /path/for/vault
    # If arguments are not provided, default to local "zettelkasten_structure.json" and current dir.
    json_file = sys.argv[1] if len(sys.argv) > 1 else "zettelkasten_structure.json"
    base_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    create_vault_structure(json_file, base_dir)
