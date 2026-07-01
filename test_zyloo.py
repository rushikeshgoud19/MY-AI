import os
import json
import urllib.request

keys = [
    "sk-zy-0a1ad246ec0759181208f467e4981a97b37a8d5e75fb8cb4",
    "sk-zy-2bd9407fd18512a198b3ee8ef74a895392f4456b142feadb"
]

url = "https://api.zyloo.io/v1/chat/completions"
data = json.dumps({
    "model": "zyloo/claude-opus-4-7",
    "messages": [{"role": "user", "content": "Reply with a single word: hello"}]
}).encode("utf-8")

for i, key in enumerate(keys):
    req = urllib.request.Request(url, data=data)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    
    print(f"Testing Key {i+1}...")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            print(f"Key {i+1} Success! Response: {result['choices'][0]['message']['content']}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Key {i+1} Failed: {e.code} - {error_body}")
    except Exception as e:
        print(f"Key {i+1} Error: {str(e)}")
    print("-" * 40)
