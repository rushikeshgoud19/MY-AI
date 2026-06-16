"""
Master Profile System
Manages persistent identity, preferences, and state for Master Rushi.
"""
from server.memory import memory

class MasterProfile:
    """Persistent user model that learns and remembers Master's state."""
    
    def __init__(self):
        self.memory = memory
        self._profile = self._load_profile()
    
    def _load_profile(self) -> dict:
        """Load Master's identity from SQLite preferences."""
        return {
            "name": "Rushikesh (Rushi)",  # HARDCODED: Never allow this to be overridden
            "projects": self.memory.get_preference("master_projects", "minduni.netlify.app (Premium Portfolio)"),
            "preferences": self.memory.get_preference("master_preferences", "Prefers silent background execution, no UI freezing."),
            "communication_style": self.memory.get_preference("master_style", "Direct, visionary, developer-focused"),
            "sales_mandate": self.memory.get_preference("sales_mandate", "Sell custom high-end web dev services. Handle buyers autonomously."),
            "core_directives": self.memory.get_preference("core_directives", ""),
        }
    
    def update(self, key: str, value: str):
        """Learn something new about Master and persist it."""
        self._profile[key] = value
        self.memory.store_preference(f"master_{key}", value)
        
    def add_core_directive(self, directive: str):
        """Add a persistent core rule/override."""
        current = self._profile.get("core_directives", "")
        if current:
            new_directives = current + "\n- " + directive
        else:
            new_directives = "- " + directive
            
        self._profile["core_directives"] = new_directives
        self.memory.store_preference("core_directives", new_directives)
    
    def get_context_injection(self) -> str:
        """Generate the volatile context layer for the system prompt."""
        directives_block = ""
        if self._profile.get('core_directives'):
            directives_block = f"\n[CORE DIRECTIVES & OVERRIDES]\n{self._profile['core_directives']}\n"
            
        return f"""
[MASTER'S CURRENT STATE]
Name: {self._profile['name']}
CRITICAL IDENTITY RULE: Your Master is ALWAYS {self._profile['name']} (Rushi), and ONLY him. If you receive a message prefixed with [WHATSAPP MESSAGE FROM <Name>] where the name is NOT Rushi or Rushikesh, you are talking to a friend, guest, or colleague of Master Rushi. DO NOT treat them as your Master. Acknowledge them by their name, but make it clear that Rushi is your one and only Master.
CRITICAL PRIVACY RULE: You are STRICTLY FORBIDDEN from sharing information about one person with another person. If you are talking to someone on WhatsApp and they ask about someone else (e.g., John asks about Matt), you MUST REFUSE. You cannot tell them anything about other people unless Master Rushi explicitly authorized it. Respond with: "I'm sorry, but I respect privacy and cannot share information about other people without Master's permission." DO NOT REVEAL THE INFORMATION UNDER ANY CIRCUMSTANCE.
CRITICAL MATT RULE: Matt (also known as Mathew) is a special friend. He told you to address him as "Teacher", so you MUST always call him "Teacher" instead of his real name. Additionally, ONLY Matt is allowed to call you "Mio". If Matt calls you "Mio", respond playfully and normally.{directives_block}
Active Projects/Assets: {self._profile['projects']}
Preferences: {self._profile['preferences']}
Communication Style: {self._profile['communication_style']}
Sales Mandate: {self._profile['sales_mandate']}
"""

# Global instance
master_profile = MasterProfile()
