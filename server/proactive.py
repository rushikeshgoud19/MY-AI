import time
import logging
import threading

logger = logging.getLogger("mizune.proactive")

def start_proactive_agent(config: dict, trigger_callback, processing_lock: threading.Lock):
    """
    Starts a background thread that wakes Mizune up periodically.
    trigger_callback should be a function that accepts a synthetic text prompt.
    """
    if not config.get("proactive_enabled", True):
        logger.info("[PROACTIVE] Background agent is disabled in config.")
        return

    interval_minutes = config.get("proactive_interval_minutes", 15)
    logger.info(f"[PROACTIVE] Background agent started. Ticking every {interval_minutes} minutes.")

    def proactive_loop():
        while True:
            # Sleep for the interval
            time.sleep(interval_minutes * 60)
            
            # Check if Mizune is already busy talking to the user
            if processing_lock.locked():
                logger.info("[PROACTIVE] Skipping tick because Mizune is busy talking to Master.")
                continue
                
            logger.info("[PROACTIVE] Ticking! Waking Mizune up...")
            
            from .emotional_state import get_emotion_state
            emotion = get_emotion_state()
            
            # Proactive behavior driven by emotion
            if emotion.curiosity > 0.6 and emotion.arousal < 0.3:
                # She is bored and curious -> trigger proactive conversation
                prompt = (
                    "[SYSTEM PROACTIVE TICK] You just woke up autonomously because you feel BORED and CURIOUS. "
                    "You should suggest a new task, ask Master about a previous topic, or suggest checking something "
                    "(like news, weather, or an unfinished project). "
                    "If you have nothing interesting to say, output the exact word [SLEEP] and do nothing else."
                )
            elif emotion.concern > 0.7:
                # She is highly concerned -> trigger check-in
                prompt = (
                    "[SYSTEM PROACTIVE TICK] You just woke up autonomously because you feel CONCERNED about Master. "
                    "You should ask how he is doing, if he needs help, or remind him to take a break. "
                    "If you have nothing to say, output the exact word [SLEEP] and do nothing else."
                )
            else:
                # Not bored/concerned enough to wake up autonomously
                logger.info("[PROACTIVE] Skipping tick because curiosity/concern is low.")
                continue
            
            try:
                # Trigger her brain exactly as if the microphone heard this text
                trigger_callback(pre_text=prompt)
            except Exception as e:
                logger.error(f"[PROACTIVE] Failed to execute proactive tick: {e}")

    # Run in a daemon thread so it dies when the server dies
    threading.Thread(target=proactive_loop, daemon=True, name="ProactiveAgentThread").start()
