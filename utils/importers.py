import csv
import io
import re
import requests
import feedparser
from bs4 import BeautifulSoup


def parse_csv(file_storage):
    """
    Parse a merchant product CSV upload.
    Expected columns: name_en, name_fr, description_en, description_fr, price
    Returns list of dicts.
    """
    stream = io.StringIO(file_storage.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    products = []
    for row in reader:
        name_en = row.get('name_en', '').strip()
        if not name_en:
            continue
        price = None
        price_on_request = False
        raw_price = row.get('price', '').strip().replace('$', '').replace(',', '')
        if raw_price.lower() in ('', 'sur demande', 'on request', 'n/a'):
            price_on_request = True
        else:
            try:
                price = float(raw_price)
            except ValueError:
                price_on_request = True

        products.append({
            'name_en':        name_en,
            'name_fr':        row.get('name_fr', '').strip(),
            'description_en': row.get('description_en', '').strip(),
            'description_fr': row.get('description_fr', '').strip(),
            'price':          price,
            'price_on_request': price_on_request,
        })
    return products


def _parse_price(text):
    """
    Extract a float price from a string like '$12.99', '12,99 $', 'CAD 45.00'.
    Returns (float, False) on success, (None, True) if no price found.
    """
    if not text:
        return None, True
    # Strip currency symbols and normalise
    cleaned = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
    # Handle cases like '12.99.00' by taking the first valid number
    match = re.search(r'\d+\.?\d*', cleaned)
    if match:
        try:
            return float(match.group()), False
        except ValueError:
            pass
    return None, True


def import_from_rss(url):
    """
    Import products from an RSS/Atom feed URL.
    Each feed entry becomes a product:
      - entry.title      → name_en
      - entry.summary    → description_en (HTML stripped)
      - price tag        → price (checked in order: price_value, g:price,
                           media:price, or parsed from title/summary)

    Works with WooCommerce RSS, Shopify RSS, custom feeds, and any
    standard RSS 2.0 / Atom feed.

    Returns (list_of_product_dicts, error_string_or_None).
    """
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        return [], f"Could not parse feed: {e}"

    if feed.bozo and not feed.entries:
        # bozo means malformed, but feedparser still tries — only fail if no entries
        return [], "Feed could not be read. Please check the URL and try again."

    if not feed.entries:
        return [], "Feed is empty or contains no products."

    products = []
    for entry in feed.entries[:50]:
        name = entry.get('title', '').strip()
        if not name:
            continue

        # Strip HTML from summary/description
        raw_summary = entry.get('summary', '') or entry.get('description', '')
        if raw_summary:
            description = BeautifulSoup(raw_summary, 'html.parser').get_text(separator=' ', strip=True)[:500]
        else:
            description = ''

        # Try to find a price in common RSS price tags
        price = None
        price_on_request = False

        # WooCommerce / Google Shopping feed tags
        price_candidates = [
            entry.get('price_value'),               # custom
            entry.get('g_price'),                   # Google Shopping
            entry.get('price'),                     # generic
        ]
        # Also check tags list (feedparser puts custom namespaced tags here)
        for tag in entry.get('tags', []):
            term = tag.get('term', '')
            if re.match(r'^\$?\d+[\d.,]*$', term.strip()):
                price_candidates.append(term)

        for candidate in price_candidates:
            if candidate:
                price, price_on_request = _parse_price(str(candidate))
                if price is not None:
                    break

        # Last resort: look for a price pattern in the title itself
        # e.g. "Widget Pro — $29.99"
        if price is None:
            match = re.search(r'\$\s*(\d+[\d.,]*)', name)
            if match:
                price, price_on_request = _parse_price(match.group(1))

        if price is None:
            price_on_request = True

        products.append({
            'name_en':          name,
            'name_fr':          '',
            'description_en':   description,
            'description_fr':   '',
            'price':            price,
            'price_on_request': price_on_request,
        })

    if not products:
        return [], "No products could be extracted from this feed."

    return products, None


def import_from_website(url):
    """
    Attempt to scrape products from a merchant website.
    Works best with WooCommerce and simple product pages.
    Returns list of dicts with name_en, description_en, price fields.
    """
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        resp = requests.get(url, timeout=8, headers={
            'User-Agent': 'Mozilla/5.0 (Citify product importer)'
        })
        resp.raise_for_status()
    except Exception as e:
        return [], f"Could not reach website: {e}"

    soup = BeautifulSoup(resp.text, 'html.parser')
    products = []

    # WooCommerce product cards
    woo_items = soup.select('li.product, .woocommerce-loop-product__link')
    if woo_items:
        for item in woo_items[:50]:
            name_tag  = item.select_one('.woocommerce-loop-product__title, h2')
            price_tag = item.select_one('.price .woocommerce-Price-amount, .price')
            name      = name_tag.get_text(strip=True)  if name_tag  else ''
            price_text = price_tag.get_text(strip=True) if price_tag else ''
            if name:
                price = None
                try:
                    price = float(price_text.replace('$', '').replace(',', '').strip())
                except Exception:
                    pass
                products.append({'name_en': name, 'description_en': '', 'price': price,
                                 'price_on_request': price is None,
                                 'name_fr': '', 'description_fr': ''})
        return products, None

    # Shopify product JSON feed
    if 'shopify' in resp.text or 'myshopify' in url:
        try:
            json_url = url.rstrip('/') + '/products.json?limit=50'
            j = requests.get(json_url, timeout=8).json()
            for p in j.get('products', []):
                variant = p['variants'][0] if p.get('variants') else {}
                price = None
                try:
                    price = float(variant.get('price', ''))
                except Exception:
                    pass
                products.append({
                    'name_en': p.get('title', ''),
                    'description_en': BeautifulSoup(p.get('body_html', ''), 'html.parser').get_text()[:300],
                    'price': price,
                    'price_on_request': price is None,
                    'name_fr': '', 'description_fr': '',
                })
            return products, None
        except Exception:
            pass

    # Generic fallback: look for any product-like headings
    for tag in soup.select('h2, h3'):
        text = tag.get_text(strip=True)
        if 5 < len(text) < 150:
            products.append({'name_en': text, 'description_en': '', 'price': None,
                             'price_on_request': True, 'name_fr': '', 'description_fr': ''})
        if len(products) >= 30:
            break

    if not products:
        return [], "No products found. CSV import may work better for this site."

    return products, None
