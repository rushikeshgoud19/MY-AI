import re, sys

def clean(text):
    text = re.sub(r'<function=.*?</function>', '', text, flags=re.DOTALL)
    text = re.sub(r'\[function=[^\]]+\]\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'<tool.*?/tool>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{.*?"type".*?"function".*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\{.*?"name".*?"parameters".*?\}', '', text, flags=re.DOTALL)
    text = text.strip()
    text = re.sub(r'^\{\s*', '', text)
    text = re.sub(r'\s*\}$', '', text)
    return text.strip()

cases = [
    ("I have opened Spotify for you, Master!",       "I have opened Spotify for you, Master!"),
    ("I have opened Spotify for you, Master! }",     "I have opened Spotify for you, Master!"),
    ("{ I have opened Spotify for you, Master!",     "I have opened Spotify for you, Master!"),
    ("{ I have opened Spotify for you, Master! }",   "I have opened Spotify for you, Master!"),
    ("Use {this} format or {that} one.",              "Use {this} format or {that} one."),
    ("}",                                             ""),
]

all_pass = True
for inp, expected in cases:
    got = clean(inp)
    ok = (got == expected)
    status = "OK  " if ok else "FAIL"
    print(f"[{status}] {repr(inp)[:55]:55s} => {repr(got)}")
    if not ok:
        print(f"       expected: {repr(expected)}")
        all_pass = False

print()
print("ALL PASS" if all_pass else "SOME FAILED")
sys.exit(0 if all_pass else 1)
