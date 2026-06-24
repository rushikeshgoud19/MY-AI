import os
import glob
import logging

logger = logging.getLogger("mizune.obsidian")

class ObsidianBridge:
    def __init__(self):
        # Default fallback, can be configured later
        self.vault_path = os.path.expanduser("~/Documents/Obsidian Vault")

    def set_vault_path(self, path: str):
        self.vault_path = path

    def read_note(self, note_name: str):
        if not os.path.exists(self.vault_path):
            return f"Error: Obsidian vault not found at {self.vault_path}"
        
        search_pattern = os.path.join(self.vault_path, "**", f"{note_name}.md")
        files = glob.glob(search_pattern, recursive=True)
        
        if not files:
            return f"Error: Note '{note_name}' not found."
            
        with open(files[0], 'r', encoding='utf-8') as f:
            return f.read()

    def write_note(self, note_name: str, content: str, folder=""):
        if not os.path.exists(self.vault_path):
            os.makedirs(self.vault_path, exist_ok=True)
            
        target_dir = os.path.join(self.vault_path, folder)
        os.makedirs(target_dir, exist_ok=True)
        
        file_path = os.path.join(target_dir, f"{note_name}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return f"Successfully wrote to {file_path}"

global_obsidian = ObsidianBridge()
