from flask import session, request


def get_lang():
    """Return current language: 'fr' or 'en'."""
    lang = session.get('lang')
    if lang in ('fr', 'en'):
        return lang
    # Auto-detect from browser Accept-Language header
    accept = request.headers.get('Accept-Language', '')
    if accept.startswith('fr'):
        return 'fr'
    return 'en'


def set_lang(lang):
    if lang in ('fr', 'en'):
        session['lang'] = lang
