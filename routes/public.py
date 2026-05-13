from flask import Blueprint, render_template, request, redirect, url_for
from models import Merchant, Product, Category, Flag
from sqlalchemy.orm import joinedload
from app import db, cache, limiter
from utils.lang import get_lang, set_lang

public_bp = Blueprint('public', __name__)

PER_PAGE = 20
PRODUCTS_PER_PAGE = 24


@public_bp.route('/lang/<lang>')
def switch_lang(lang):
    set_lang(lang)
    return redirect(request.referrer or url_for('public.index'))


@public_bp.route('/')
@cache.cached(timeout=120, key_prefix='homepage')
def index():
    lang = get_lang()
    categories = Category.query.all()
    featured = Merchant.query.filter_by(is_active=True)\
        .options(joinedload(Merchant.category))\
        .order_by(Merchant.created_at.desc()).limit(12).all()
    return render_template('public/index.html',
                           categories=categories,
                           featured=featured,
                           lang=lang)


@public_bp.route('/search')
def search():
    lang     = get_lang()
    q        = request.args.get('q', '').strip()
    cat_slug = request.args.get('category', '')
    page     = request.args.get('page', 1, type=int)

    query = Merchant.query.filter_by(is_active=True)\
        .options(joinedload(Merchant.category))

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                Merchant.business_name.ilike(like),
                Merchant.description_en.ilike(like),
                Merchant.description_fr.ilike(like),
                Merchant.neighbourhood.ilike(like),
            )
        )

    if cat_slug:
        cat = Category.query.filter_by(slug=cat_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)

    pagination = query.order_by(Merchant.business_name).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    categories = Category.query.all()
    return render_template('public/search.html',
                           merchants=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           q=q, cat_slug=cat_slug,
                           lang=lang)


@public_bp.route('/category/<slug>')
def category(slug):
    lang     = get_lang()
    cat      = Category.query.filter_by(slug=slug).first_or_404()
    page     = request.args.get('page', 1, type=int)
    pagination = Merchant.query.filter_by(
        category_id=cat.id, is_active=True
    ).order_by(Merchant.business_name).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    categories = Category.query.all()
    return render_template('public/category.html',
                           cat=cat, merchants=pagination.items,
                           pagination=pagination,
                           categories=categories, lang=lang)


@public_bp.route('/merchant/<slug>')
def merchant_profile(slug):
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True).first_or_404()
    page     = request.args.get('page', 1, type=int)
    pagination = Product.query.filter_by(
        merchant_id=merchant.id, is_active=True
    ).paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)
    return render_template('public/merchant.html',
                           merchant=merchant,
                           products=pagination.items,
                           pagination=pagination,
                           lang=lang)


@public_bp.route('/merchant/<slug>/product/<int:product_id>')
def product_detail(slug, product_id):
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True).first_or_404()
    product  = Product.query.filter_by(id=product_id, merchant_id=merchant.id,
                                       is_active=True).first_or_404()
    return render_template('public/product.html',
                           merchant=merchant, product=product, lang=lang)


@public_bp.route('/flag/<int:merchant_id>', methods=['POST'])
@limiter.limit('3 per hour')
def flag_merchant(merchant_id):
    merchant = Merchant.query.get_or_404(merchant_id)
    reason   = request.form.get('reason', '')
    ip       = request.remote_addr
    flag = Flag(merchant_id=merchant.id, reason=reason, reporter_ip=ip)
    merchant.flag_count += 1
    db.session.add(flag)
    db.session.commit()
    return redirect(url_for('public.merchant_profile', slug=merchant.slug))


@public_bp.route('/about')
def about():
    lang = get_lang()
    return render_template('public/about.html', lang=lang)


@public_bp.route('/tos')
def tos():
    lang = get_lang()
    return render_template('public/tos.html', lang=lang)


@public_bp.route('/privacy')
def privacy():
    lang = get_lang()
    return render_template('public/privacy.html', lang=lang)




@public_bp.route('/api/subcategories/<int:cat_id>')
def api_subcategories(cat_id):
    from models import Subcategory
    from flask import jsonify
    from utils.lang import get_lang
    lang = get_lang()
    subs = Subcategory.query.filter_by(category_id=cat_id).all()
    return jsonify([{'id': s.id, 'name': s.name_fr if lang == 'fr' else s.name_en} for s in subs])

@public_bp.route('/sitemap.xml')
def sitemap():
    merchants  = Merchant.query.filter_by(is_active=True).all()
    categories = Category.query.all()
    return render_template('sitemap.xml',
                           merchants=merchants,
                           categories=categories), 200, {'Content-Type': 'application/xml'}
