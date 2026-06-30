import bleach

# Tags allowed in merchant descriptions (basic formatting only)
ALLOWED_TAGS = ['b', 'i', 'em', 'strong', 'br', 'p', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {}


def clean_text(value):
    """Strip all HTML and dangerous content from plain text fields."""
    if not value:
        return ''
    return bleach.clean(value.strip(), tags=[], attributes={}, strip=True)


def clean_rich(value):
    """Allow basic safe HTML tags in description fields."""
    if not value:
        return ''
    return bleach.clean(value.strip(), tags=ALLOWED_TAGS,
                        attributes=ALLOWED_ATTRIBUTES, strip=True)


def clean_url(value):
    """Validate and sanitise a URL field."""
    if not value:
        return ''
    value = value.strip()
    # Only allow http and https URLs
    if value and not value.startswith(('http://', 'https://')):
        value = 'https://' + value
    # Bleach linkify safety check
    cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)
    return cleaned
