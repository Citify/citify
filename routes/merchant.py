from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import Product, ProductImage, Category
from app import db, limiter, invalidate_public_cache
from utils.lang import get_lang
from utils.geocode import geocode
from utils.importers import parse_csv, import_from_website
from utils.sanitise import clean_text, clean_rich, clean_url

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


@merchant_bp.route('/dashboard')
@login_required
def dashboard():
    lang     = get_lang()
    products = Product.query.filter_by(
        merchant_id=current_user.id, is_active=True
    ).order_by(Product.created_at.desc()).all()
    return render_template('merchant/dashboard.html',
                           merchant=current_user, products=products, lang=lang)


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

        neq = clean_text(request.form.get('neq', ''))
        current_user.neq         = neq
        current_user.is_verified = bool(neq)

        cat_id = request.form.get('category_id', type=int)
        sub_id = request.form.get('subcategory_id', type=int)
        current_user.category_id    = cat_id
        current_user.subcategory_id = sub_id

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
                           merchant=current_user, categories=categories, lang=lang)


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

        product = Product(
            merchant_id      = current_user.id,
            name_en          = name_en,
            name_fr          = clean_text(request.form.get('name_fr', '')),
            description_en   = clean_rich(request.form.get('description_en', '')),
            description_fr   = clean_rich(request.form.get('description_fr', '')),
            price            = price,
            price_on_request = price_on_request,
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
            # Sanitise imported data
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
            imported, error = import_from_website(url)
            if request.form.get('confirm') and imported:
                count = 0
                for p in imported:
                    p['name_en']        = clean_text(p.get('name_en', ''))
                    p['description_en'] = clean_rich(p.get('description_en', ''))
                    if not p['name_en']:
                        continue
                    product = Product(merchant_id=current_user.id, **p)
                    db.session.add(product)
                    count += 1
                db.session.commit()
                flash(f'{count} products imported! / {count} produits importes!', 'success')
                return redirect(url_for('merchant.dashboard'))

    return render_template('merchant/import_website.html',
                           lang=lang, imported=imported, error=error)
