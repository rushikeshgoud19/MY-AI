import datetime
from server.memory_tree import memory_tree_db
from server.config import log_info

class EvolutionBudget:
    def __init__(self, daily_limit_dollars: float = 0.20):
        self.daily_limit_dollars = daily_limit_dollars

    def get_today_date(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _ensure_today_record(self, cursor, today: str):
        cursor.execute("INSERT OR IGNORE INTO evolution_budget (date, tokens_used, cost_dollars) VALUES (?, 0, 0.0)", (today,))

    def get_spend_today(self) -> float:
        try:
            cursor = memory_tree_db.db.cursor()
            today = self.get_today_date()
            self._ensure_today_record(cursor, today)
            memory_tree_db.db.commit()
            
            cursor.execute("SELECT cost_dollars FROM evolution_budget WHERE date = ?", (today,))
            row = cursor.fetchone()
            return row[0] if row else 0.0
        except Exception as e:
            log_info(f"[EVOLUTION BUDGET] Error reading budget: {e}")
            return 0.0

    def can_evolve(self) -> bool:
        """Returns True if there is still budget left today."""
        spent = self.get_spend_today()
        return spent < self.daily_limit_dollars

    def record_usage(self, tokens: int, cost: float):
        try:
            cursor = memory_tree_db.db.cursor()
            today = self.get_today_date()
            self._ensure_today_record(cursor, today)
            
            cursor.execute("UPDATE evolution_budget SET tokens_used = tokens_used + ?, cost_dollars = cost_dollars + ? WHERE date = ?", (tokens, cost, today))
            memory_tree_db.db.commit()
            log_info(f"[EVOLUTION BUDGET] Recorded ${cost:.4f} spend. Total today: ${self.get_spend_today():.4f}")
        except Exception as e:
            log_info(f"[EVOLUTION BUDGET] Error recording usage: {e}")

# Global instance
evolution_budget = EvolutionBudget()
