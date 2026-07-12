import sys
sys.path.append("c:\\Users\\rushi\\OneDrive\\Desktop\\my Ai")
from server.web_agent import headless_web_agent

if __name__ == "__main__":
    result = headless_web_agent(
        url="https://example.com",
        objective="Find out what domain this is for.",
        visible=False
    )
    print("\nFINAL RESULT:")
    print(result)
