import bleach

def sanitize_message(content):
    return bleach.clean(content, tags=[], attributes={}, styles=[], strip=True)