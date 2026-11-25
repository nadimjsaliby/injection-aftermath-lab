import re


def slugify(text):
    """Turn a title into a URL slug."""
    text = text.strip().lower()
    return re.sub(r"\s+", "-", text)
