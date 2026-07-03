import sys
import os
from server.ai import get_ai_response
from server.config import load_config
try:
    print(get_ai_response('What time is it right now? Give me exactly the time in hours and minutes.', [], load_config()))
except Exception as e:
    print("Error:", e)
