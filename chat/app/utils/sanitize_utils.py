import bleach

def sanitize_message(content):
    if content is None:
        return ''
    if not isinstance(content, str):
        content = str(content)
        
    return bleach.clean(content, tags=[], attributes={}, strip=True)