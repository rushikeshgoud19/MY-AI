import requests
import json

API_KEY = "ap2_906cbf61-69aa-4228-be64-4c5a8db355f5"
URL = "https://api.murf.ai/v1/speech/voices"

headers = {
    "api-key": API_KEY
}

response = requests.get(URL, headers=headers)
if response.status_code == 200:
    voices = response.json()
# Filter for Japanese or voices that might have the right accent
    for v in voices:
        lang = str(v.get('language', '')).lower()
        id_str = str(v['voiceId']).lower()
        if "japanese" in lang or "jp" in id_str or "accent" in lang:
            print(f"ID: {v['voiceId']}, Name: {v['displayName']}, Lang: {v.get('language')}, Gender: {v['gender']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
