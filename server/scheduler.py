import os
import time
import sqlite3
import threading
import datetime
import logging
from croniter import croniter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CronManager:
    def __init__(self, db_path="data/schedules.db"):
        self.db_path = db_path
        self.is_running = False
        self.thread = None
        self.task_callback = None
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create one-time tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS one_time_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                trigger_time TEXT NOT NULL,
                executed INTEGER DEFAULT 0
            )
        ''')
        
        # Create recurring tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                last_executed TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_one_time_task(self, description: str, trigger_time_iso: str):
        """Add a one-time task using an ISO 8601 string (e.g. '2026-06-17T08:00:00')"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO one_time_tasks (description, trigger_time) VALUES (?, ?)', 
                       (description, trigger_time_iso))
        conn.commit()
        conn.close()
        logger.info(f"Added one-time task: '{description}' at {trigger_time_iso}")
        return True

    def add_recurring_task(self, description: str, cron_expression: str):
        """Add a recurring task using a standard cron expression (e.g. '0 8 * * *')"""
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO recurring_tasks (description, cron_expression) VALUES (?, ?)', 
                       (description, cron_expression))
        conn.commit()
        conn.close()
        logger.info(f"Added recurring task: '{description}' on cron '{cron_expression}'")
        return True

    def _background_loop(self):
        logger.info("Scheduler background loop started.")
        while self.is_running:
            try:
                self._check_and_execute_tasks()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
            time.sleep(60) # Wake up every 60 seconds

    @staticmethod
    def _as_aware(dt):
        """Legacy rows were stored naive from the server's UTC clock — pin them to
        UTC so aware/naive comparisons can't crash or drift. New rows are aware IST."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    def _check_and_execute_tasks(self):
        from server.config import mizune_now, mizune_tz
        now = mizune_now()
        # try/finally: the two SELECTs below sit OUTSIDE the per-task try blocks, so a
        # schema change or a locked DB propagated out of here with the connection still
        # open. _background_loop swallows the exception and runs again in 60 seconds —
        # forever — so a single recurring failure leaked a connection a minute.
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:

            # Check one-time tasks
            cursor.execute('SELECT id, description, trigger_time FROM one_time_tasks WHERE executed = 0')
            one_time_tasks = cursor.fetchall()
            for task_id, description, trigger_time_str in one_time_tasks:
                try:
                    trigger_time = self._as_aware(datetime.datetime.fromisoformat(trigger_time_str))
                    if now >= trigger_time:
                        logger.info(f"Executing scheduled one-time task: {description}")
                        if self.task_callback:
                            # Send task to callback asynchronously to avoid blocking the scheduler
                            threading.Thread(target=self.task_callback, args=(description,)).start()
                    
                        # Mark as executed
                        cursor.execute('UPDATE one_time_tasks SET executed = 1 WHERE id = ?', (task_id,))
                except Exception as e:
                    logger.error(f"Failed to parse or execute task {task_id}: {e}")

            # Check recurring tasks
            cursor.execute('SELECT id, description, cron_expression, last_executed FROM recurring_tasks')
            recurring_tasks = cursor.fetchall()
            for task_id, description, cron_expression, last_executed_str in recurring_tasks:
                try:
                    base_time = self._as_aware(datetime.datetime.fromisoformat(last_executed_str)) if last_executed_str else now - datetime.timedelta(minutes=2)
                    # Evaluate cron in Master's timezone so "0 8 * * *" means 8 AM IST, not UTC.
                    base_time = base_time.astimezone(mizune_tz())
                    cron = croniter(cron_expression, base_time)
                    next_trigger = cron.get_next(datetime.datetime)
                
                    # If the next trigger time is in the past (up to now), execute it!
                    if now >= next_trigger:
                         logger.info(f"Executing scheduled recurring task: {description}")
                         if self.task_callback:
                             threading.Thread(target=self.task_callback, args=(description,)).start()
                     
                         # Update last executed time
                         cursor.execute('UPDATE recurring_tasks SET last_executed = ? WHERE id = ?', (now.isoformat(), task_id))
                except Exception as e:
                    logger.error(f"Failed to process recurring task {task_id}: {e}")

            conn.commit()
        finally:
            conn.close()

    def start(self, task_callback=None):
        """Starts the background scheduler thread."""
        self.task_callback = task_callback
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._background_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Stops the background scheduler thread."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
