import re
_URL=re.compile(r'https?://|t\.me/|www\.',re.I)

def looks_spam(text):
    if not text: return False
    if len(text)>4000: return True
    if len(_URL.findall(text))>=4: return True
    compact=''.join(ch for ch in text.lower() if ch.isalnum())
    return len(compact)>30 and len(set(compact))/len(compact)<0.08
