import bleach

def sanitize_message(content):
    """
    Clean user-provided message content before storing / emitting.

    Uses bleach.clean with empty allowed tags/attributes (strip any HTML).
    Defensively handles non-string content by converting to str or returning ''.
    """
    if content is None:
        return ''
    # Ensure we only sanitize strings
    if not isinstance(content, str):
        content = str(content)

    # Note: some bleach versions don't accept 'styles' or other kwargs.
    # Keep the call simple and compatible:
    return bleach.clean(content, tags=[], attributes={}, strip=True)