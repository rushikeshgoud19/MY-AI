import re
import time
from typing import List, Dict, Any

from .memory_tree import memory_tree_db
from .config import log_info

class EntityExtractor:
    """
    Lightweight entity extraction to detect 'hot' topics in conversations and background data.
    """
    
    # Common words to ignore for hotness
    STOP_WORDS = {"the", "and", "a", "an", "is", "it", "to", "of", "in", "for", "on", "with", "as", "by", "at", "master", "mizune", "i", "my", "me", "you", "your", "what", "how", "when", "where", "why"}
    
    def extract_and_score(self, content: str) -> List[Dict[str, Any]]:
        """
        Extracts entities and updates their hotness scores in the database.
        Returns a list of 'hot' entities that deserve their own topic tree.
        """
        if not content: return []
        
        # 1. Simple Regex Extraction (Capitalized Words / Tech terms)
        # This is a fast heuristic before falling back to LLMs for deep analysis.
        words = re.findall(r'\b[A-Z][a-z0-9]+\b|\b[A-Z]{2,}\b|\b[a-z]+-[a-z]+\b', content)
        
        entities = {}
        for w in words:
            w_lower = w.lower()
            if w_lower in self.STOP_WORDS or len(w_lower) < 3:
                continue
            entities[w_lower] = entities.get(w_lower, 0) + 1
            
        if not entities: return []
        
        hot_entities = []
        now = time.time()
        
        try:
            cursor = memory_tree_db.db.cursor()
            
            for entity_name, count in entities.items():
                entity_id = f"ent_{entity_name}"
                
                # Check if exists
                cursor.execute("SELECT hotness_score FROM entities WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                
                if row:
                    # Update existing (bump hotness)
                    new_hotness = row[0] + (0.5 * count)
                    cursor.execute(
                        "UPDATE entities SET hotness_score = ?, last_seen = ? WHERE id = ?",
                        (new_hotness, now, entity_id)
                    )
                else:
                    # Insert new
                    new_hotness = 1.0 * count
                    cursor.execute(
                        "INSERT INTO entities (id, name, type, hotness_score, last_seen, first_seen) VALUES (?, ?, ?, ?, ?, ?)",
                        (entity_id, entity_name, 'auto', new_hotness, now, now)
                    )
                    
                # Threshold for a topic tree
                HOTNESS_THRESHOLD = 5.0
                if new_hotness >= HOTNESS_THRESHOLD:
                    hot_entities.append({"id": entity_id, "name": entity_name, "hotness": new_hotness})
                    
            memory_tree_db.db.commit()
            return hot_entities
            
        except Exception as e:
            log_info(f"[ENTITY EXTRACTOR] Error extracting: {e}")
            return []

entity_extractor = EntityExtractor()
