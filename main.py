#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------------------
# 1. CONFIGURATION: PATHS, API KEYS, ETC.
# ---------------------------------------------------------------------

load_dotenv()

JSON_FILE_PATH = "data/result_small.json"
OUTPUT_DIRECTORY = "MyInterestsVault"

PROMPT_ANALYSIS_FILE = "prompts/analysis_prompt.txt"

OBSIDIAN_CONFIG = {
    "name": "MyInterestsVault",
    "dir": ".obsidian",
    "settings": {
        "core-plugins": {
            "file-explorer": True,
            "search": True,
        },
        "theme": "obsidian",
    },
}

# ---------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------------------------

def simplify_json(data_str):
    data = json.loads(data_str)
    simplified_messages = []

    for message in data.get("messages", []):
        text_content = ""
        links = []
        
        for part in message.get("text", []):
            if isinstance(part, str):
                text_content += part
            elif isinstance(part, dict) and part.get("type") == "link":
                links.append(part.get("text"))

        simplified_messages.append({
            "date": message.get("date"),
            "text": text_content.strip(),
            "links": links
        })

    return json.dumps(simplified_messages, indent=4)

def load_prompt_from_file(file_path: str) -> str:
    print(f"[DEBUG] Loading prompt from: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] Prompt file not found: {file_path}")
        return ""

def call_chatgpt_api(prompt: str, max_tokens: int = 400000, temperature: float = 0.7):
    print(f"[DEBUG] Sending prompt to ChatGPT API. Max tokens: {max_tokens}, Temperature: {temperature}")
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
        )
        response = completion.choices[0].message.content
        print(f"[DEBUG] API call successful. Response length: {len(response)} characters")
        return response
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        return ""

def create_markdown_file(file_path: Path, content: str):
    try:
        print(f"[DEBUG] Creating file: {file_path}")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[INFO] File created: {file_path}")
    except Exception as e:
        print(f"[ERROR] Failed to create file {file_path}: {e}")

def create_obsidian_config(base_path: Path):
    """
    Creates Obsidian Vault configuration files.
    """
    try:
        print(f"[INFO] Creating Obsidian configuration...")
        obsidian_dir = base_path / OBSIDIAN_CONFIG["dir"]
        obsidian_dir.mkdir(parents=True, exist_ok=True)

        settings_file = obsidian_dir / "app.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(OBSIDIAN_CONFIG["settings"], f, indent=4)

        print(f"[INFO] Obsidian configuration created in {obsidian_dir}")
    except Exception as e:
        print(f"[ERROR] Failed to create Obsidian configuration: {e}")

def show_directory_tree(dir_path: str, prefix: str = ""):
    dir_path_obj = Path(dir_path)
    if not dir_path_obj.exists():
        print(f"[WARNING] Directory does not exist: {dir_path}")
        return
    entries = sorted(dir_path_obj.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    for i, entry in enumerate(entries):
        connector = "└──" if i == len(entries) - 1 else "├──"
        print(prefix + connector + " " + entry.name)
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            show_directory_tree(entry, prefix + extension)

# ---------------------------------------------------------------------
# 3. MAIN FUNCTION
# ---------------------------------------------------------------------

def analyze_and_generate_structure():
    # Load prompts
    analysis_prompt = load_prompt_from_file(PROMPT_ANALYSIS_FILE)
    if not analysis_prompt:
        print("[ERROR] Analysis prompt is empty. Exiting.")
        return

    # Load JSON data
    data_json = json.dumps(load_json_data(JSON_FILE_PATH), ensure_ascii=False, indent=2)
    if not data_json:
        print("[ERROR] JSON data is empty or invalid. Exiting.")
        return

    simplified_data_json = simplify_json(data_str = data_json)
    with open('simplified_data_json.txt', "w", encoding="utf-8") as f:
        f.write(simplified_data_json)

    analysis_prompt = analysis_prompt.format(language=os.getenv("VAULT_LANG"), json_data=simplified_data_json)

    # Analyze JSON
    generation_result = call_chatgpt_api(f"{analysis_prompt}")
    if not generation_result:
        print("[ERROR] Failed to generate structure from API. Exiting.")
        return

    # Parse generation result
    generation_result = generation_result.replace("```json", "").replace("```", "")

    print("=== ANALYSIS RESULT ===\n", generation_result, "\n")
    with open('generation_result.txt', "w", encoding="utf-8") as f:
        f.write(generation_result)

    try:
        structure_data = json.loads(generation_result)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse generation result as JSON: {e}")
        return

    # Create folders and files
    base_path = Path(OUTPUT_DIRECTORY)
    for folder in structure_data.get("folders", []):
        folder_path = base_path / folder["name"]
        try:
            print(f"[INFO] Creating folder: {folder_path}")
            folder_path.mkdir(parents=True, exist_ok=True)
            for file in folder.get("files", []):
                create_markdown_file(folder_path / file["name"], file["content"])
            for subfolder in folder.get("subfolders", []):
                subfolder_path = folder_path / subfolder["name"]
                print(f"[INFO] Creating subfolder: {subfolder_path}")
                subfolder_path.mkdir(parents=True, exist_ok=True)
                for file in subfolder.get("files", []):
                    create_markdown_file(subfolder_path / file["name"], file["content"])
        except Exception as e:
            print(f"[ERROR] Failed to create folder structure for {folder_path}: {e}")

    # Create Obsidian configuration
    create_obsidian_config(base_path)

    # Show directory tree
    print("=== CREATED STRUCTURE ===")
    show_directory_tree(OUTPUT_DIRECTORY)

def load_json_data(json_path: str) -> dict:
    print(f"[DEBUG] Loading JSON data from: {json_path}")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] JSON file not found: {json_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode error: {e}")
        return {}

def main():
    analyze_and_generate_structure()

if __name__ == "__main__":
    main()
