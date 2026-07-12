"""
Emotion detection module for Mizune AI.
"""
import re

__all__ = ["EMOTION_PATTERNS", "detect_emotion"]

# ─── Emotion Detection Patterns ──────────────────────────────────────────────
# Map words/phrases to 3D avatar facial blendshapes
EMOTION_PATTERNS = {
    "happy": [
        r"\b(yay|happy|glad|love|awesome|great|good|nice|hehe|haha|lol)\b",
        r"\b(arigatou|thanks|thank you)\b",
        r":\)|:D|\^\^|\^_\^"
    ],
    "sad": [
        r"\b(sad|sorry|apologies|bad|terrible|awful|cry|tears|gomen|gomen ne)\b",
        r":\(|:_;|T_T|;;"
    ],
    "angry": [
        r"\b(angry|mad|hate|stupid|idiot|annoying|frustrated|grr)\b",
        r">\.<|:@|>:\("
    ],
    "surprised": [
        r"\b(wow|whoa|omg|gosh|really|eh\?|nani|ehh)\b",
        r":o|:O|o\.o|O\.O"
    ],
    "thinking": [
        r"\b(hmm|thinking|wondering|maybe|let me check|calculating|processing)\b",
        r"\b(let's see|let me see|wait)\b"
    ],
    "blush": [
        r"\b(embarrassed|shy|flattered|blush|aww)\b",
        r">\/\/<|\*blush\*"
    ],
    "excited": [
        r"\b(excited|can't wait|omg yes|woohoo|yippee)\b",
        r"!!"
    ],
    "sleepy": [
        r"\b(sleepy|tired|yawn|goodnight|bedtime|zzz)\b",
        r"-_-"
    ]
}

from traceroot import observe, update_current_span
@observe(name="emotion.analyze", type="agent")
def detect_emotion(text: str) -> str:
    """Analyze text and return the dominant emotion, or 'neutral'."""
    update_current_span(metadata={"text_preview": text[:50]})
    text_lower = text.lower()
    
    # First check explicit tags like [EMOTION: happy]
    match = re.search(r"\[EMOTION:\s*([^\]]+)\]", text_lower)
    if match:
        emo = match.group(1).strip()
        if emo in EMOTION_PATTERNS or emo == "neutral":
            return emo
            
    # Then fallback to keyword matching
    for emotion, patterns in EMOTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return emotion
                
    return "neutral"
