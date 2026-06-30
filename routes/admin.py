from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from models import Merchant, Product, Flag, ProductImage, Category
from app import db
from utils.lang import get_lang
from utils.mail import send_seed_welcome_email

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    lang          = get_lang()
    total_merchants = Merchant.query.filter_by(is_active=True).count()
    total_products  = Product.query.filter_by(is_active=True).count()
    flagged         = Merchant.query.filter(Merchant.flag_count > 0).order_by(
                        Merchant.flag_count.desc()).all()
    recent          = Merchant.query.order_by(Merchant.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_merchants=total_merchants,
                           total_products=total_products,
                           flagged=flagged,
                           recent=recent,
                           lang=lang)


@admin_bp.route('/merchants')
@login_required
@admin_required
def merchants():
    lang   = get_lang()
    page   = request.args.get('page', 1, type=int)
    q      = request.args.get('q', '').strip()
    query  = Merchant.query
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                Merchant.business_name.ilike(like),
                Merchant.email.ilike(like),
                Merchant.neighbourhood.ilike(like),
            )
        )
    merchants = query.order_by(Merchant.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/merchants.html', merchants=merchants, lang=lang, q=q)


@admin_bp.route('/merchant/<int:merchant_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_merchant(merchant_id):
    merchant = Merchant.query.get_or_404(merchant_id)
    merchant.is_active = False
    db.session.commit()
    flash(f'{merchant.business_name} deactivated.', 'success')
    return redirect(url_for('admin.merchants'))


@admin_bp.route('/merchant/<int:merchant_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_merchant(merchant_id):
    merchant = Merchant.query.get_or_404(merchant_id)
    merchant.is_active = True
    merchant.flag_count = 0
    db.session.commit()
    flash(f'{merchant.business_name} activated.', 'success')
    return redirect(url_for('admin.merchants'))


@admin_bp.route('/merchant/<int:merchant_id>/feature', methods=['POST'])
@login_required
@admin_required
def feature_merchant(merchant_id):
    from datetime import datetime, timedelta
    merchant = Merchant.query.get_or_404(merchant_id)
    months = request.form.get('months', 1, type=int)
    merchant.is_featured    = True
    merchant.featured_until = datetime.utcnow() + timedelta(days=30*months)
    db.session.commit()
    flash(f'{merchant.business_name} is now featured for {months} month(s).', 'success')
    return redirect(url_for('admin.merchants'))


@admin_bp.route('/merchant/<int:merchant_id>/unfeature', methods=['POST'])
@login_required
@admin_required
def unfeature_merchant(merchant_id):
    merchant = Merchant.query.get_or_404(merchant_id)
    merchant.is_featured    = False
    merchant.featured_until = None
    db.session.commit()
    flash(f'{merchant.business_name} is no longer featured.', 'success')
    return redirect(url_for('admin.merchants'))


@admin_bp.route('/flags')
@login_required
@admin_required
def flags():
    lang  = get_lang()
    flags = Flag.query.filter_by(reviewed=False).order_by(
        Flag.created_at.desc()).all()
    return render_template('admin/flags.html', flags=flags, lang=lang)


@admin_bp.route('/flag/<int:flag_id>/dismiss', methods=['POST'])
@login_required
@admin_required
def dismiss_flag(flag_id):
    flag = Flag.query.get_or_404(flag_id)
    flag.reviewed = True
    db.session.commit()
    return redirect(url_for('admin.flags'))


@admin_bp.route('/seed', methods=['GET', 'POST'])
@login_required
@admin_required
def seed_merchant():
    import secrets, json
    from utils.lang import get_lang
    from utils.importers import import_from_website, import_from_rss
    from utils.sanitise import clean_text, clean_url
    from utils.neighbourhoods import NEIGHBOURHOODS
    from routes.auth import make_slug

    lang       = get_lang()
    categories = Category.query.all()
    imported   = []
    error      = None
    merchant   = None

    if request.method == 'POST':
        business_name  = clean_text(request.form.get('business_name', ''))
        website        = clean_url(request.form.get('website', ''))
        rss_url        = clean_url(request.form.get('rss_url', ''))
        neighbourhood  = clean_text(request.form.get('neighbourhood', ''))
        category_id    = request.form.get('category_id', type=int)
        address        = clean_text(request.form.get('address', ''))
        phone          = clean_text(request.form.get('phone', ''))
        instagram      = clean_text(request.form.get('instagram', ''))
        description    = clean_text(request.form.get('description_en', ''))
        description_fr = clean_text(request.form.get('description_fr', ''))

        if not business_name:
            flash('Business name required.', 'error')
            return redirect(url_for('admin.seed_merchant'))

        slug = make_slug(business_name)

        merchant = Merchant(
            email          = f"unclaimed-{slug}@seed.citify.ca",
            business_name  = business_name,
            slug           = slug,
            website        = website,
            rss_url        = rss_url,
            neighbourhood  = neighbourhood,
            category_id    = category_id,
            address        = address,
            phone          = phone,
            instagram      = instagram,
            description_en = description,
            description_fr = description_fr,
            is_active      = True,
            is_claimed     = False,
            is_verified    = False,
            auto_sync      = True,
        )
        merchant.set_password(secrets.token_hex(32))
        db.session.add(merchant)
        db.session.flush()

        # Scrape products
        scrape_url = website or rss_url
        if scrape_url:
            if rss_url:
                imported, error = import_from_rss(rss_url)
            else:
                imported, error = import_from_website(website)

            for p in imported:
                name_en = p.get('name_en', '').strip()
                if not name_en:
                    continue
                product = Product(
                    merchant_id      = merchant.id,
                    name_en          = name_en,
                    name_fr          = p.get('name_fr', ''),
                    description_en   = p.get('description_en', ''),
                    description_fr   = p.get('description_fr', ''),
                    price            = p.get('price'),
                    price_on_request = p.get('price_on_request', True),
                    is_active        = True,
                )
                db.session.add(product)
                db.session.flush()

                image_url = p.get('image_url', '')
                if image_url and image_url.startswith('http'):
                    if 'cdn.shopify.com' in image_url:
                        sep = '&' if '?' in image_url else '?'
                        image_url = image_url + sep + 'format=jpg&width=1200'
                    db.session.add(ProductImage(
                        product_id    = product.id,
                        image_url     = image_url,
                        thumbnail_url = image_url,
                    ))

        # Delivery + affiliate fields
        merchant.offers_delivery          = bool(request.form.get('offers_delivery'))
        merchant.delivery_url             = request.form.get('delivery_url', '').strip() or None
        merchant.third_party_delivery_url = request.form.get('third_party_delivery_url', '').strip() or None
        merchant.affiliate_suffix         = request.form.get('affiliate_suffix', '').strip() or None
        merchant.affiliate_url            = request.form.get('affiliate_url', '').strip() or None

        # Generate claim token so the welcome email has a working claim link
        from datetime import datetime, timedelta
        token = secrets.token_urlsafe(32)
        merchant.claim_token         = token
        merchant.claim_token_expires = datetime.utcnow() + timedelta(hours=48)

        
       # Auto-send welcome email with claim link
        real_email = request.form.get('contact_email', '').strip()
        if real_email:
            claim_link = url_for('auth.claim_verify',
                                 slug=merchant.slug,
                                 token=token,
                                 _external=True)
            send_seed_welcome_email(merchant, claim_link, to_email=real_email)

        db.session.commit()
        flash(f'Seeded {merchant.business_name} with {len(imported)} products. / {merchant.business_name} ajouté avec {len(imported)} produits.', 'success')
        return redirect(url_for('admin.seed_merchant'))

    return render_template('admin/seed.html',
                           categories=categories,
                           neighbourhoods=NEIGHBOURHOODS,
                           lang=lang)


@admin_bp.route('/merchant/<int:merchant_id>/toggle-auto-sync', methods=['POST'])
@login_required
@admin_required
def toggle_auto_sync(merchant_id):
    merchant = Merchant.query.get_or_404(merchant_id)
    merchant.auto_sync = not merchant.auto_sync
    db.session.commit()
    state = 'enabled' if merchant.auto_sync else 'disabled'
    flash(f'Auto-sync {state} for {merchant.business_name}.', 'success')
    return redirect(url_for('admin.merchants'))
