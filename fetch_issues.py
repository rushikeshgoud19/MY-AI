import urllib.request
import json
import sys

def get_issues(repo="traceroot-ai/traceroot", state="open", per_page=30):
    url = f"https://api.github.com/repos/{repo}/issues?state={state}&per_page={per_page}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            for item in data:
                is_pr = "pull_request" in item
                item_type = "PR" if is_pr else "ISSUE"
                labels = [l["name"] for l in item.get("labels", [])]
                print(f"[{item_type}] #{item['number']} {item['title']}")
                print(f"   Labels: {labels}")
                print(f"   URL: {item['html_url']}")
                print("-" * 50)
    except Exception as e:
        print(f"Error fetching issues: {e}")

if __name__ == "__main__":
    get_issues()
