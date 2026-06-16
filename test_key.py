import os
from openai import OpenAI

def test_key():
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Set OPENROUTER_API_KEY env var first!")
        return
    base_url = "https://openrouter.ai/api/v1"
    
    try:
        print("Authenticating with OpenRouter...")
        client = OpenAI(
            api_key=api_key, 
            base_url=base_url
        )
        
        print("\nSearching for matching free models...")
        models = client.models.list()
        target_model = None
        for m in models.data:
            if 'free' in m.id.lower():
                print(f"Found Free Model: {m.id}")
                # check if there's any 120b or something similar
                if '120b' in m.id.lower() or 'oss' in m.id.lower() or 'gpt' in m.id.lower():
                    target_model = m.id
        
        if not target_model:
            # Let's just pick any popular free model as a default if we can't find a 120b one
            target_model = "meta-llama/llama-3-8b-instruct:free" 
            print("\nCould not find '120b' or 'oss' free model. Going to test with a fallback free model to ensure the key works.")
            
        print(f"\nTesting generation with model: {target_model}...")
        response = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": "Reply with one word: Success"}],
            max_tokens=10
        )
        print(f"Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_key()
