"""
Bilingual search synonym expansion for Citify Montreal.
Maps common French search terms to their English equivalents and vice versa,
so a search in either language surfaces results in both.
"""

SYNONYMS = {
    # Food & Drink
    'restaurant': ['restaurant', 'resto', 'eatery', 'dining'],
    'resto': ['restaurant', 'resto'],
    'cafe': ['cafe', 'café', 'coffee', 'coffeeshop'],
    'café': ['cafe', 'café', 'coffee'],
    'coffee': ['coffee', 'cafe', 'café'],
    'boulangerie': ['boulangerie', 'bakery', 'patisserie', 'pastry'],
    'bakery': ['bakery', 'boulangerie', 'patisserie', 'pastry'],
    'patisserie': ['patisserie', 'pastry', 'boulangerie', 'bakery'],
    'pastry': ['pastry', 'patisserie', 'boulangerie'],
    'epicerie': ['epicerie', 'épicerie', 'grocery', 'grocer'],
    'épicerie': ['epicerie', 'épicerie', 'grocery', 'grocer'],
    'grocery': ['grocery', 'epicerie', 'épicerie'],
    'traiteur': ['traiteur', 'catering'],
    'catering': ['catering', 'traiteur'],

    # Retail
    'vetements': ['vetements', 'vêtements', 'clothing', 'clothes', 'fashion'],
    'vêtements': ['vetements', 'vêtements', 'clothing', 'clothes', 'fashion'],
    'clothing': ['clothing', 'clothes', 'vetements', 'vêtements'],
    'bijoux': ['bijoux', 'bijouterie', 'jewellery', 'jewelry'],
    'bijouterie': ['bijouterie', 'bijoux', 'jewellery', 'jewelry'],
    'jewellery': ['jewellery', 'jewelry', 'bijoux', 'bijouterie'],
    'jewelry': ['jewelry', 'jewellery', 'bijoux', 'bijouterie'],
    'livres': ['livres', 'books', 'librairie', 'bookstore'],
    'books': ['books', 'livres', 'librairie', 'bookstore'],
    'librairie': ['librairie', 'bookstore', 'books', 'livres'],
    'bookstore': ['bookstore', 'librairie', 'books', 'livres'],
    'vintage': ['vintage', 'seconde main', 'secondhand', 'used'],
    'secondhand': ['secondhand', 'second hand', 'vintage', 'seconde main'],
    'cadeaux': ['cadeaux', 'gifts', 'gift'],
    'gifts': ['gifts', 'gift', 'cadeaux'],

    # Health & Beauty
    'coiffure': ['coiffure', 'coiffeur', 'hair', 'salon', 'barbershop'],
    'coiffeur': ['coiffeur', 'coiffure', 'hair', 'salon'],
    'hair': ['hair', 'coiffure', 'coiffeur', 'salon'],
    'beaute': ['beaute', 'beauté', 'beauty', 'salon'],
    'beauté': ['beaute', 'beauté', 'beauty'],
    'beauty': ['beauty', 'beaute', 'beauté'],
    'spa': ['spa', 'well-being', 'bien-etre', 'bien-être', 'wellness'],
    'wellness': ['wellness', 'spa', 'bien-etre', 'bien-être'],
    'pharmacie': ['pharmacie', 'pharmacy', 'drugstore'],
    'pharmacy': ['pharmacy', 'pharmacie'],
    'fitness': ['fitness', 'gym', 'sport', 'sports'],
    'gym': ['gym', 'fitness', 'sport'],

    # Services
    'nettoyage': ['nettoyage', 'cleaning'],
    'cleaning': ['cleaning', 'nettoyage'],
    'renovation': ['renovation', 'rénovation', 'contractor', 'construction'],
    'rénovation': ['renovation', 'rénovation', 'contractor'],
    'plomberie': ['plomberie', 'plumbing'],
    'plumbing': ['plumbing', 'plomberie'],
    'electricite': ['electricite', 'électricité', 'electrical', 'electric'],
    'électricité': ['electricite', 'électricité', 'electrical'],
    'electrical': ['electrical', 'electricite', 'électricité'],
    'tutorat': ['tutorat', 'tutoring', 'education'],
    'tutoring': ['tutoring', 'tutorat'],

    # Other
    'animaux': ['animaux', 'pets', 'animal'],
    'pets': ['pets', 'animaux', 'animal'],
    'technologie': ['technologie', 'technology', 'tech'],
    'technology': ['technology', 'technologie', 'tech'],
    'automobile': ['automobile', 'automotive', 'car', 'auto'],
    'automotive': ['automotive', 'automobile', 'car', 'auto'],
    'enfants': ['enfants', 'children', 'kids', 'famille', 'family'],
    'children': ['children', 'enfants', 'kids'],
    'famille': ['famille', 'family', 'enfants', 'children'],
    'family': ['family', 'famille', 'children', 'enfants'],
    'maison': ['maison', 'home', 'house'],
    'home': ['home', 'maison'],
    'jardin': ['jardin', 'garden'],
    'garden': ['garden', 'jardin'],
}


def expand_query(q):
    """
    Given a search term, return a list of terms to search for.
    Always includes the original term. Adds synonyms if found.
    """
    terms = [q]
    lower = q.lower().strip()
    if lower in SYNONYMS:
        terms = list(set(SYNONYMS[lower]))
    return terms
