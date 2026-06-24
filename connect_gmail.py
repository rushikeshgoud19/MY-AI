import os
import json
import socket
import urllib.request
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

print("=========================================")
print("Connect Mizune to Gmail (OAuth2)")
print("=========================================")

import os
import json

try:
    with open("config.json", "r") as f:
        config_data = json.load(f)
        CLIENT_ID = config_data.get("google_client_id", "")
        CLIENT_SECRET = config_data.get("google_client_secret", "")
except Exception:
    CLIENT_ID = ""
    CLIENT_SECRET = ""

if not CLIENT_ID or not CLIENT_SECRET:
    print("Client ID and Secret are required.")
    exit(1)

redirect_uri = 'http://localhost:8080/'
auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    "response_type=code&"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
    "scope=https://www.googleapis.com/auth/gmail.readonly&"
    "access_type=offline&"
    "prompt=consent"
)

auth_code = None

class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        
        if 'code' in query:
            auth_code = query['code'][0]
            self.wfile.write(b"<html><body><h1>Success!</h1><p>You can close this window and return to the terminal.</p></body></html>")
        else:
            self.wfile.write(b"<html><body><h1>Failed</h1><p>No code found.</p></body></html>")
            
    def log_message(self, format, *args):
        pass # Suppress logs

print("\nOpening your browser to authenticate...")
webbrowser.open(auth_url)

print("Waiting for you to log in and approve...")
server = HTTPServer(('localhost', 8080), AuthHandler)
while not auth_code:
    server.handle_request()

print(f"Received auth code! Exchanging for tokens...")

# Exchange code for token
data = urllib.parse.urlencode({
    'code': auth_code,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri': redirect_uri,
    'grant_type': 'authorization_code'
}).encode('utf-8')

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
try:
    with urllib.request.urlopen(req) as response:
        token_data = json.loads(response.read().decode())
        
        # Save to Mizune's token directory
        token_dir = ".data/tokens"
        os.makedirs(token_dir, exist_ok=True)
        token_path = os.path.join(token_dir, "google_token.json")
        
        with open(token_path, "w") as f:
            json.dump(token_data, f)
            
        print(f"\nSUCCESS! Token saved to {token_path}")
        print("Mizune's background polling engine will now start reading your emails!")
except urllib.error.HTTPError as e:
    print(f"\nError exchanging token: {e.read().decode()}")
