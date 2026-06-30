from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import Product, ProductImage, Category, PageView, Location
from app import db, limiter, invalidate_public_cache
from utils.lang import get_lang
from utils.geocode import geocode
from utils.importers import parse_csv, import_from_rss, import_from_website
import json
from utils.sanitise import clean_text, clean_rich, clean_url
from utils.neighbourhoods import NEIGHBOURHOODS

merchant_bp = Blueprint('merchant', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def try_upload(file_storage):
    from flask import current_app
    if not current_app.config.get('B2_KEY_ID'):
        return '/static/img/placeholder.jpg', '/static/img/placeholder.jpg'
    from utils.images import process_and_upload
    return process_and_upload(file_storage)


def _save_product_with_image(p, merchant_id):
    name_en = clean_text(p.get('name_en', ''))
    if not name_en:
        return None

    product = Product(
        merchant_id      = merchant_id,
        name_en          = name_en,
        name_fr          = clean_text(p.get('name_fr', '')),
        description_en   = clean_rich(p.get('description_en', '')),
        description_fr   = clean_rich(p.get('description_fr', '')),
        price            = p.get('price'),
        price_on_request = p.get('price_on_request', True),
        is_active        = True,
    )
    db.session.add(product)
    db.session.flush()

    source_image_url = p.get('image_url', '')
    if source_image_url and source_image_url.startswith('http'):
        if 'cdn.shopify.com' in source_image_url:
            sep = '&' if '?' in source_image_url else '?'
            source_image_url = source_image_url + sep + 'format=jpg&width=1200'
        db.session.add(ProductImage(
            product_id    = product.id,
            image_url     = source_image_url,
            thumbnail_url = source_image_url,
        ))

    return product


@merchant_bp.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime, timedelta
    from sqlalchemy import func
    lang     = get_lang()
    products = Product.query.filter_by(
        merchant_id=current_user.id, is_active=True
    ).order_by(Product.created_at.desc()).all()

    # Analytics — last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    seven_days_ago  = datetime.utcnow() - timedelta(days=7)

    views_30d = PageView.query.filter(
        PageView.merchant_id == current_user.id,
        PageView.event_type == 'profile_view',
        PageView.created_at >= thirty_days_ago
    ).count()

    views_7d = PageView.query.filter(
        PageView.merchant_id == current_user.id,
        PageView.event_type == 'profile_view',
        PageView.created_at >= seven_days_ago
    ).count()

    product_clicks_30d = PageView.query.filter(
        PageView.merchant_id == current_user.id,
        PageView.event_type == 'product_view',
        PageView.created_at >= thirty_days_ago
    ).count()

    # Daily views for sparkline — last 14 days
    daily_views = []
    for i in range(13, -1, -1):
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end   = day_start + timedelta(days=1)
        count = PageView.query.filter(
            PageView.merchant_id == current_user.id,
            PageView.event_type == 'profile_view',
            PageView.created_at >= day_start,
            PageView.created_at < day_end,
        ).count()
        daily_views.append(count)

    return render_template('merchant/dashboard.html',
                           merchant=current_user, products=products, lang=lang,
                           views_30d=views_30d, views_7d=views_7d,
                           product_clicks_30d=product_clicks_30d,
                           daily_views=daily_views)


@merchant_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    lang       = get_lang()
    categories = Category.query.all()

    if request.method == 'POST':
        current_user.business_name  = clean_text(request.form.get('business_name', ''))
        current_user.description_en = clean_rich(request.form.get('description_en', ''))
        current_user.description_fr = clean_rich(request.form.get('description_fr', ''))
        current_user.address        = clean_text(request.form.get('address', ''))
        current_user.neighbourhood  = clean_text(request.form.get('neighbourhood', ''))
        current_user.phone          = clean_text(request.form.get('phone', ''))
        current_user.website        = clean_url(request.form.get('website', ''))
        current_user.whatsapp       = clean_text(request.form.get('whatsapp', ''))
        current_user.instagram      = clean_text(request.form.get('instagram', ''))
        current_user.facebook       = clean_url(request.form.get('facebook', ''))
        current_user.rss_url        = clean_url(request.form.get('rss_url', ''))
        current_user.video_url      = clean_url(request.form.get('video_url', ''))
        current_user.newsletter_url = clean_url(request.form.get('newsletter_url', '')) or None
        # Promotion
        if request.form.get('clear_promo'):
            current_user.promo_title   = None
            current_user.promo_body    = None
            current_user.promo_url     = None
            current_user.promo_expires = None
        else:
            current_user.promo_title = request.form.get('promo_title', '').strip()[:200] or None
            current_user.promo_body  = request.form.get('promo_body',  '').strip()[:500] or None
            current_user.promo_url   = clean_url(request.form.get('promo_url', '')) or None
            raw_exp = request.form.get('promo_expires', '').strip()
            if raw_exp:
                from datetime import date as _date
                try:
                    current_user.promo_expires = _date.fromisoformat(raw_exp)
                except ValueError:
                    current_user.promo_expires = None
            else:
                current_user.promo_expires = None
        current_user.offers_delivery          = bool(request.form.get('offers_delivery'))
        current_user.delivery_url             = request.form.get('delivery_url', '').strip() or None
        current_user.third_party_delivery_url = request.form.get('third_party_delivery_url', '').strip() or None
        current_user.affiliate_suffix         = request.form.get('affiliate_suffix', '').strip() or None

        neq = clean_text(request.form.get('neq', ''))
        current_user.neq         = neq
        current_user.is_verified = bool(neq)

        cat_id = request.form.get('category_id', type=int)
        sub_id = request.form.get('subcategory_id', type=int)
        current_user.category_id    = cat_id
        current_user.subcategory_id = sub_id

        # Save opening hours
        days = ['mon','tue','wed','thu','fri','sat','sun']
        hours = {}
        for d in days:
            hours[d] = {
                'open':   request.form.get(f'hours_open_{d}',  '09:00'),
                'close':  request.form.get(f'hours_close_{d}', '17:00'),
                'closed': f'hours_closed_{d}' in request.form,
            }
        current_user.hours_json = json.dumps(hours)

        if current_user.address:
            lat, lon = geocode(current_user.address)
            if lat:
                current_user.latitude  = lat
                current_user.longitude = lon

        logo = request.files.get('logo')
        if logo and allowed_file(logo.filename):
            from utils.images import upload_logo
            current_user.logo_url = upload_logo(logo, current_user.slug)

        db.session.commit()
        invalidate_public_cache()
        flash('Profile updated! / Profil mis a jour!', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('merchant/profile.html',
                           merchant=current_user, categories=categories,
                           neighbourhoods=NEIGHBOURHOODS, lang=lang)


@merchant_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
@limiter.limit("60 per hour")
def add_product():
    lang       = get_lang()
    categories = Category.query.all()

    if request.method == 'POST':
        name_en = clean_text(request.form.get('name_en', ''))
        if not name_en:
            flash('Product name (English) is required.', 'error')
            return redirect(url_for('merchant.add_product'))

        price_on_request = 'price_on_request' in request.form
        price = None
        if not price_on_request:
            raw = request.form.get('price', '').strip().replace('$', '').replace(',', '')
            try:
                price = float(raw)
            except ValueError:
                price_on_request = True

        is_on_sale = 'is_on_sale' in request.form
        sale_price = None
        if is_on_sale:
            raw_sale = request.form.get('sale_price', '').strip().replace('$', '').replace(',', '')
            try:
                sale_price = float(raw_sale)
            except ValueError:
                sale_price = None

        product = Product(
            merchant_id      = current_user.id,
            name_en          = name_en,
            name_fr          = clean_text(request.form.get('name_fr', '')),
            description_en   = clean_rich(request.form.get('description_en', '')),
            description_fr   = clean_rich(request.form.get('description_fr', '')),
            price            = price,
            price_on_request = price_on_request,
            is_on_sale       = is_on_sale,
            sale_price       = sale_price,
            category_id      = request.form.get('category_id', type=int),
        )
        db.session.add(product)
        db.session.flush()

        for f in request.files.getlist('images'):
            if f and allowed_file(f.filename):
                full_url, thumb_url = try_upload(f)
                img = ProductImage(product_id=product.id,
                                   image_url=full_url, thumbnail_url=thumb_url)
                db.session.add(img)

        db.session.commit()
        invalidate_public_cache()
        flash('Product added! / Produit ajoute!', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('merchant/add_product.html', categories=categories, lang=lang)


@merchant_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    lang       = get_lang()
    product    = Product.query.filter_by(
        id=product_id, merchant_id=current_user.id).first_or_404()
    categories = Category.query.all()

    if request.method == 'POST':
        product.name_en        = clean_text(request.form.get('name_en', ''))
        product.name_fr        = clean_text(request.form.get('name_fr', ''))
        product.description_en = clean_rich(request.form.get('description_en', ''))
        product.description_fr = clean_rich(request.form.get('description_fr', ''))
        product.category_id    = request.form.get('category_id', type=int)

        product.price_on_request = 'price_on_request' in request.form
        if not product.price_on_request:
            raw = request.form.get('price', '').strip().replace('$', '').replace(',', '')
            try:
                product.price = float(raw)
            except ValueError:
                product.price_on_request = True

        product.is_on_sale = 'is_on_sale' in request.form
        product.sale_price = None
        if product.is_on_sale:
            raw_sale = request.form.get('sale_price', '').strip().replace('$', '').replace(',', '')
            try:
                product.sale_price = float(raw_sale)
            except ValueError:
                product.sale_price = None

        for f in request.files.getlist('images'):
            if f and allowed_file(f.filename):
                full_url, thumb_url = try_upload(f)
                img = ProductImage(product_id=product.id,
                                   image_url=full_url, thumbnail_url=thumb_url)
                db.session.add(img)

        db.session.commit()
        flash('Product updated! / Produit mis a jour!', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('merchant/edit_product.html',
                           product=product, categories=categories, lang=lang)


@merchant_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(
        id=product_id, merchant_id=current_user.id).first_or_404()
    product.is_active = False
    db.session.commit()
    invalidate_public_cache()
    flash('Product removed. / Produit supprime.', 'success')
    return redirect(url_for('merchant.dashboard'))


@merchant_bp.route('/import/csv', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def import_csv():
    lang = get_lang()
    if request.method == 'POST':
        f = request.files.get('csv_file')
        if not f or not f.filename.endswith('.csv'):
            flash('Please upload a .csv file.', 'error')
            return redirect(url_for('merchant.import_csv'))

        products_data = parse_csv(f)
        count = 0
        for p in products_data:
            p['name_en']        = clean_text(p.get('name_en', ''))
            p['name_fr']        = clean_text(p.get('name_fr', ''))
            p['description_en'] = clean_rich(p.get('description_en', ''))
            p['description_fr'] = clean_rich(p.get('description_fr', ''))
            if not p['name_en']:
                continue
            product = Product(merchant_id=current_user.id, **p)
            db.session.add(product)
            count += 1
        db.session.commit()
        flash(f'{count} products imported! / {count} produits importes!', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('merchant/import_csv.html', lang=lang)


@merchant_bp.route('/import/rss', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def import_rss():
    lang        = get_lang()
    imported    = []
    error       = None
    prefill_url = current_user.rss_url or ''

    if request.method == 'POST':
        url = clean_url(request.form.get('url', ''))

        if url and url != current_user.rss_url:
            current_user.rss_url = url
            db.session.commit()

        if url:
            if request.form.get('confirm') and request.form.get('imported_json'):
                try:
                    products_data = json.loads(request.form.get('imported_json'))
                except Exception:
                    flash('Import error. Please try again.', 'error')
                    return redirect(url_for('merchant.import_rss'))

                count = 0
                for p in products_data:
                    product = _save_product_with_image(p, current_user.id)
                    if product:
                        count += 1

                db.session.commit()
                invalidate_public_cache()
                flash(f'{count} products imported! / {count} produits importes!', 'success')
                return redirect(url_for('merchant.dashboard'))
            else:
                imported, error = import_from_rss(url)
                prefill_url = url

    return render_template('merchant/import_rss.html',
                           lang=lang,
                           imported=imported,
                           error=error,
                           prefill_url=prefill_url)


@merchant_bp.route('/import/website', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour")
def import_website():
    lang     = get_lang()
    imported = []
    error    = None

    if request.method == 'POST':
        url = clean_url(request.form.get('url', ''))

        if url:
            if request.form.get('confirm') and request.form.get('imported_json'):
                try:
                    products_data = json.loads(request.form.get('imported_json'))
                except Exception:
                    flash('Import error. Please try again.', 'error')
                    return redirect(url_for('merchant.import_website'))

                count = 0
                for p in products_data:
                    product = _save_product_with_image(p, current_user.id)
                    if product:
                        count += 1

                db.session.commit()
                invalidate_public_cache()
                flash(f'{count} products imported! / {count} produits importes!', 'success')
                return redirect(url_for('merchant.dashboard'))
            else:
                imported, error = import_from_website(url)

    return render_template('merchant/import_website.html',
                           lang=lang, imported=imported, error=error)

@merchant_bp.route('/marketing')
@login_required
def marketing():
    lang = get_lang()
    profile_url = f"https://citify.ca/merchant/{current_user.slug}"
    return render_template('merchant/marketing.html',
                           lang=lang,
                           merchant=current_user,
                           profile_url=profile_url)

# ── Multiple Locations ────────────────────────────────────────────────────────

@merchant_bp.route('/locations')
@login_required
def locations():
    lang = get_lang()
    locs = Location.query.filter_by(merchant_id=current_user.id).order_by(Location.id).all()
    return render_template('merchant/locations.html', lang=lang, locations=locs)

@merchant_bp.route('/locations/add', methods=['POST'])
@login_required
def location_add():
    label_en  = request.form.get('label_en', '').strip()[:200]
    label_fr  = request.form.get('label_fr', '').strip()[:200]
    address   = request.form.get('address',  '').strip()[:300]
    try:
        lat = float(request.form.get('latitude',  ''))
        lon = float(request.form.get('longitude', ''))
    except (ValueError, TypeError):
        lat = lon = None
    loc = Location(
        merchant_id=current_user.id,
        label_en=label_en,
        label_fr=label_fr,
        address=address,
        latitude=lat,
        longitude=lon,
    )
    db.session.add(loc)
    db.session.commit()
    flash('Location added. / Adresse ajoutée.', 'success')
    return redirect(url_for('merchant.locations'))

@merchant_bp.route('/locations/<int:loc_id>/edit', methods=['POST'])
@login_required
def location_edit(loc_id):
    loc = Location.query.filter_by(id=loc_id, merchant_id=current_user.id).first_or_404()
    loc.label_en = request.form.get('label_en', '').strip()[:200]
    loc.label_fr = request.form.get('label_fr', '').strip()[:200]
    loc.address  = request.form.get('address',  '').strip()[:300]
    try:
        loc.latitude  = float(request.form.get('latitude',  ''))
        loc.longitude = float(request.form.get('longitude', ''))
    except (ValueError, TypeError):
        loc.latitude = loc.longitude = None
    db.session.commit()
    flash('Location updated. / Adresse mise à jour.', 'success')
    return redirect(url_for('merchant.locations'))

@merchant_bp.route('/locations/<int:loc_id>/delete', methods=['POST'])
@login_required
def location_delete(loc_id):
    loc = Location.query.filter_by(id=loc_id, merchant_id=current_user.id).first_or_404()
    db.session.delete(loc)
    db.session.commit()
    flash('Location removed. / Adresse supprimée.', 'success')
    return redirect(url_for('merchant.locations'))
