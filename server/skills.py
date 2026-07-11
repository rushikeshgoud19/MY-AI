import os
import importlib.util
import logging
import json
import time
import shutil
from typing import Dict, Any, Callable
from .config import log_info
from .memory_tree import memory_tree_db

__all__ = ["SkillManager", "skill_manager"]

class SkillManager:
    def __init__(self, data_dir: str = ".data/skills"):
        self.data_dir = data_dir
        self.skills_dir = os.path.join(data_dir, "active")
        self.archive_dir = os.path.join(data_dir, "archive")
        self.staging_dir = os.path.join(data_dir, "staging")
        self.meta_file = os.path.join(data_dir, "skills_meta.json")
        
        for d in [self.skills_dir, self.archive_dir, self.staging_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
                
        self.loaded_skills: Dict[str, Callable] = {}
        self.metadata: Dict[str, Any] = self._load_metadata()
        self.load_all_skills()
        
    def _load_metadata(self) -> Dict[str, Any]:
        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
        
    def _save_metadata(self):
        try:
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=4)
        except Exception as e:
            log_info(f"[SKILLS] Failed to save metadata: {e}")

    def load_all_skills(self):
        self.loaded_skills.clear()
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".py"):
                skill_name = filename[:-3]
                # Security Check: Only load if it is explicitly approved in metadata
                meta = self.metadata.get(skill_name, {})
                if meta.get("status") != "active":
                    log_info(f"[SKILLS] Blocked auto-loading of unapproved skill: {skill_name}")
                    continue
                self._load_skill_file(skill_name, os.path.join(self.skills_dir, filename))
                
    def _load_skill_file(self, skill_name: str, filepath: str):
        try:
            spec = importlib.util.spec_from_file_location(skill_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'execute'):
                self.loaded_skills[skill_name] = getattr(module, 'execute')
                log_info(f"[SKILLS] Successfully loaded skill: {skill_name}")
            else:
                log_info(f"[SKILLS] Skill {skill_name} is missing 'execute' function.")
        except Exception as e:
            log_info(f"[SKILLS] Failed to load skill {skill_name}: {e}")

    def _init_skill_meta(self, name: str, desc: str, version: int = 1):
        self.metadata[name] = {
            "description": desc,
            "version": version,
            "created_at": time.time(),
            "last_used": 0,
            "use_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "tags": [],
            "status": "active"
        }
        self._save_metadata()

    def create_skill(self, name: str, description: str, code: str, requires_approval: bool = True) -> str:
        """
        Create a new skill programmatically (distillation).
        New skills are staged and require approval, and scanned for security.
        """
        from .security import SecurityScanner
        is_safe, reason = SecurityScanner.scan_code(code)
        if not is_safe:
            msg = f"Security scan failed for skill '{name}': {reason}"
            log_info(f"[SKILL MANAGER] {msg}")
            return msg
            
        return self._create_skill_internal(name, description, code, requires_approval)
        
    def _create_skill_internal(self, name: str, description: str, code: str, requires_approval: bool) -> str:
        # Determine target directory
        target_dir = self.staging_dir if requires_approval else self.skills_dir
        filepath = os.path.join(target_dir, f"{name}.py")
        
        # Versioning: Archive old if exists in active
        active_filepath = os.path.join(self.skills_dir, f"{name}.py")
        if os.path.exists(active_filepath) and not requires_approval:
            old_version = self.metadata.get(name, {}).get("version", 1)
            archive_name = f"{name}_v{old_version}_{int(time.time())}.py"
            shutil.copy(active_filepath, os.path.join(self.archive_dir, archive_name))
            new_version = old_version + 1
        else:
            new_version = 1
        
        # Add metadata header
        full_code = f'"""\nDescription: {description}\nVersion: {new_version}\n"""\n\n{code}'
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(full_code)
                
            if not requires_approval:
                self._load_skill_file(name, filepath)
                if name in self.metadata:
                    self.metadata[name]["version"] = new_version
                    self.metadata[name]["description"] = description
                else:
                    self._init_skill_meta(name, description, new_version)
                self._save_metadata()
                
                # Store memory of this skill
                chunk_id = f"skill_{name}_{int(time.time())}"
                memory_tree_db.insert_chunk(chunk_id, "skills", f"Distilled skill '{name}' (v{new_version}): {description}", len(description)//4, {"name": name})
                
            return True
        except Exception as e:
            log_info(f"[SKILLS] Error creating skill {name}: {e}")
            return False
            
    def execute_skill(self, name: str, *args, **kwargs) -> Any:
        if name not in self.loaded_skills:
            return f"Error: Skill '{name}' not found."
            
        meta = self.metadata.get(name, {})
        meta["use_count"] = meta.get("use_count", 0) + 1
        meta["last_used"] = time.time()
        
        try:
            result = self.loaded_skills[name](*args, **kwargs)
            # Basic heuristic: if result is a string containing error, count as fail
            res_str = str(result).lower()
            if "error" in res_str or "failed" in res_str or "traceback" in res_str:
                meta["fail_count"] = meta.get("fail_count", 0) + 1
            else:
                meta["success_count"] = meta.get("success_count", 0) + 1
                
            self._save_metadata()
            return result
        except Exception as e:
            meta["fail_count"] = meta.get("fail_count", 0) + 1
            self._save_metadata()
            
            err_msg = f"Error executing skill '{name}': {e}"
            log_info(f"[SKILLS] {err_msg}")
            return err_msg
            
    def get_skill_descriptions(self) -> str:
        desc_list = []
        for name in self.loaded_skills:
            meta = self.metadata.get(name, {})
            desc = meta.get("description", "No description")
            success_rate = 0
            total = meta.get("success_count", 0) + meta.get("fail_count", 0)
            if total > 0:
                success_rate = int((meta.get("success_count", 0) / total) * 100)
                
            stats = f"(v{meta.get('version', 1)} | {meta.get('use_count', 0)} uses | {success_rate}% success)"
            desc_list.append(f"- **{name}** {stats}: {desc}")
                
        return "\n".join(desc_list) if desc_list else "No skills loaded."

skill_manager = SkillManager()
