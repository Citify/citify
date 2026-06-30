NEIGHBOURHOODS = [
    {"slug": "plateau-mont-royal",   "en": "Plateau-Mont-Royal",   "fr": "Plateau-Mont-Royal"},
    {"slug": "mile-end",             "en": "Mile End",              "fr": "Mile-End"},
    {"slug": "rosemont",             "en": "Rosemont",              "fr": "Rosemont"},
    {"slug": "verdun",               "en": "Verdun",                "fr": "Verdun"},
    {"slug": "lasalle",              "en": "LaSalle",               "fr": "LaSalle"},
    {"slug": "villeray",             "en": "Villeray",              "fr": "Villeray"},
    {"slug": "hochelaga",            "en": "Hochelaga",             "fr": "Hochelaga"},
    {"slug": "saint-henri",          "en": "Saint-Henri",           "fr": "Saint-Henri"},
    {"slug": "outremont",            "en": "Outremont",             "fr": "Outremont"},
    {"slug": "westmount",            "en": "Westmount",             "fr": "Westmount"},
    {"slug": "cote-des-neiges",      "en": "Côte-des-Neiges",      "fr": "Côte-des-Neiges"},
    {"slug": "notre-dame-de-grace",  "en": "Notre-Dame-de-Grâce",  "fr": "Notre-Dame-de-Grâce"},
    {"slug": "pointe-saint-charles", "en": "Pointe-Saint-Charles",  "fr": "Pointe-Saint-Charles"},
    {"slug": "little-italy",         "en": "Little Italy",          "fr": "Petite Italie"},
    {"slug": "chinatown",            "en": "Chinatown",             "fr": "Quartier chinois"},
    {"slug": "old-montreal",         "en": "Old Montreal",          "fr": "Vieux-Montréal"},
    {"slug": "downtown",             "en": "Downtown",              "fr": "Centre-ville"},
    {"slug": "griffintown",          "en": "Griffintown",           "fr": "Griffintown"},
    {"slug": "mont-royal",           "en": "Mont-Royal",            "fr": "Mont-Royal"},
    {"slug": "parc-extension",       "en": "Parc-Extension",        "fr": "Parc-Extension"},
]

# For quick lookup by slug
BY_SLUG = {n["slug"]: n for n in NEIGHBOURHOODS}

# For matching free-text values already in the database
TEXT_TO_SLUG = {
    "verdun": "verdun",
    "lasalle": "lasalle",
    "la salle": "lasalle",
    "plateau": "plateau-mont-royal",
    "plateau-mont-royal": "plateau-mont-royal",
    "plateau mont royal": "plateau-mont-royal",
    "mile end": "mile-end",
    "mile-end": "mile-end",
    "rosemont": "rosemont",
    "villeray": "villeray",
    "hochelaga": "hochelaga",
    "saint-henri": "saint-henri",
    "saint henri": "saint-henri",
    "outremont": "outremont",
    "westmount": "westmount",
    "cote-des-neiges": "cote-des-neiges",
    "côte-des-neiges": "cote-des-neiges",
    "ndg": "notre-dame-de-grace",
    "notre-dame-de-grace": "notre-dame-de-grace",
    "notre-dame-de-grâce": "notre-dame-de-grace",
    "pointe-saint-charles": "pointe-saint-charles",
    "little italy": "little-italy",
    "petite italie": "little-italy",
    "chinatown": "chinatown",
    "quartier chinois": "chinatown",
    "old montreal": "old-montreal",
    "vieux-montréal": "old-montreal",
    "vieux montreal": "old-montreal",
    "downtown": "downtown",
    "centre-ville": "downtown",
    "griffintown": "griffintown",
    "mont-royal": "mont-royal",
    "parc-extension": "parc-extension",
    "parc extension": "parc-extension",
}


def get_neighbourhood_name(slug, lang='en'):
    n = BY_SLUG.get(slug)
    if not n:
        return slug.replace('-', ' ').title()
    return n[lang]


def slug_from_text(text):
    """Convert free-text neighbourhood to canonical slug."""
    return TEXT_TO_SLUG.get(text.lower().strip())
