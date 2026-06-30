from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import Merchant, Product, Category, Flag, PageView, Message, Rating
from sqlalchemy.orm import joinedload
from app import db, cache, limiter
from utils.lang import get_lang, set_lang
from utils.synonyms import expand_query
from utils.neighbourhoods import BY_SLUG, NEIGHBOURHOODS, get_neighbourhood_name

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
        .order_by(Merchant.is_featured.desc(), Merchant.created_at.desc()).limit(12).all()
    return render_template('public/index.html',
                           categories=categories,
                           featured=featured,
                           neighbourhoods=NEIGHBOURHOODS,
                           lang=lang)


@public_bp.route('/search')
def search():
    lang     = get_lang()
    q        = request.args.get('q', '').strip()
    cat_slug = request.args.get('category', '')
    on_sale   = request.args.get('on_sale', '')
    price_min = request.args.get('price_min', '', type=str)
    price_max = request.args.get('price_max', '', type=str)
    page      = request.args.get('page', 1, type=int)

    query = Merchant.query.filter_by(is_active=True)\
        .options(joinedload(Merchant.category))
    if q:
        terms = expand_query(q)
        merchant_filters = []
        for term in terms:
            like = f'%{term}%'
            merchant_filters.extend([
                Merchant.business_name.ilike(like),
                Merchant.description_en.ilike(like),
                Merchant.description_fr.ilike(like),
                Merchant.neighbourhood.ilike(like),
            ])
        query = query.filter(db.or_(*merchant_filters))
    if cat_slug:
        cat = Category.query.filter_by(slug=cat_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)

    pagination = query.order_by(
        Merchant.is_featured.desc(),
        Merchant.business_name
    ).paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Product search — runs when q is set OR when sale/price filters are active
    products = []
    if q or on_sale or price_min or price_max:
        product_query = Product.query.filter_by(is_active=True)\
            .join(Merchant).filter(Merchant.is_active==True)

        if q:
            terms = expand_query(q)
            product_filters = []
            for term in terms:
                like = f'%{term}%'
                product_filters.extend([
                    Product.name_en.ilike(like),
                    Product.name_fr.ilike(like),
                    Product.description_en.ilike(like),
                    Product.description_fr.ilike(like),
                ])
            product_query = product_query.filter(db.or_(*product_filters))

        if on_sale:
            product_query = product_query.filter(Product.is_on_sale == True)

        if price_min:
            try:
                pmin = float(price_min)
                product_query = product_query.filter(
                    db.or_(
                        db.and_(Product.is_on_sale == True, Product.sale_price >= pmin),
                        db.and_(Product.is_on_sale == False, Product.price >= pmin),
                    )
                )
            except ValueError:
                pass

        if price_max:
            try:
                pmax = float(price_max)
                product_query = product_query.filter(
                    db.or_(
                        db.and_(Product.is_on_sale == True, Product.sale_price <= pmax),
                        db.and_(Product.is_on_sale == False, Product.price <= pmax),
                    )
                )
            except ValueError:
                pass

        products = product_query\
            .order_by(Product.is_on_sale.desc(), Product.name_en)\
            .limit(24).all()

    categories = Category.query.all()
    return render_template('public/search.html',
                           on_sale=on_sale,
                           price_min=price_min,
                           price_max=price_max,
                           merchants=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           products=products,
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
    ptype    = request.args.get('type', '').strip()
    q        = request.args.get('q', '').strip()
    product_types = [
        row[0] for row in db.session.query(Product.product_type)
        .filter(Product.merchant_id == merchant.id, Product.is_active == True,
                Product.product_type != None, Product.product_type != '')
        .distinct().order_by(Product.product_type).all()
    ]
    product_query = Product.query.filter_by(merchant_id=merchant.id, is_active=True)
    if ptype:
        product_query = product_query.filter(Product.product_type == ptype)
    if q:
        like = f'%{q}%'
        product_query = product_query.filter(
            db.or_(Product.name_en.ilike(like), Product.name_fr.ilike(like))
        )
    pagination = product_query.order_by(Product.is_on_sale.desc(), Product.created_at.desc()).paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)
    # Log profile view (skip bots and the merchant themselves)
    try:
        from flask_login import current_user
        is_own = current_user.is_authenticated and current_user.id == merchant.id
        ua = request.headers.get('User-Agent', '').lower()
        is_bot = any(b in ua for b in ['bot', 'crawl', 'spider', 'slurp', 'fetch'])
        if not is_own and not is_bot:
            db.session.add(PageView(merchant_id=merchant.id, event_type='profile_view'))
            db.session.commit()
    except Exception:
        pass
    ratings = Rating.query.filter_by(merchant_id=merchant.id)\
                          .order_by(Rating.created_at.desc()).limit(10).all()
    return render_template('public/merchant.html',
                           merchant=merchant,
                           products=pagination.items,
                           product_types=product_types,
                           selected_type=ptype,
                           search_query=q,
                           pagination=pagination,
                           ratings=ratings,
                           lang=lang)


@public_bp.route('/merchant/<slug>/product/<int:product_id>')
def product_detail(slug, product_id):
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True).first_or_404()
    product  = Product.query.filter_by(id=product_id, merchant_id=merchant.id,
                                       is_active=True).first_or_404()
    # Log product view
    try:
        from flask_login import current_user
        is_own = current_user.is_authenticated and current_user.id == merchant.id
        ua = request.headers.get('User-Agent', '').lower()
        is_bot = any(b in ua for b in ['bot', 'crawl', 'spider', 'slurp', 'fetch'])
        if not is_own and not is_bot:
            db.session.add(PageView(merchant_id=merchant.id, event_type='product_view', product_id=product.id))
            db.session.commit()
    except Exception:
        pass
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
    flash('Report submitted. Thank you. / Signalement envoyé. Merci.', 'success')
    return redirect(url_for('public.merchant_profile', slug=merchant.slug))




@public_bp.route('/montreal/<neighbourhood_slug>')
def neighbourhood(neighbourhood_slug):
    lang = get_lang()
    n = BY_SLUG.get(neighbourhood_slug)
    if not n:
        return render_template('errors/404.html'), 404
    name = n['fr'] if lang == 'fr' else n['en']
    # Match both English and French neighbourhood names
    merchants = Merchant.query.filter_by(is_active=True).filter(
        db.or_(
            Merchant.neighbourhood.ilike(n['en']),
            Merchant.neighbourhood.ilike(n['fr']),
        )
    ).options(joinedload(Merchant.category)).order_by(Merchant.business_name).all()
    categories = Category.query.all()
    return render_template('public/neighbourhood.html',
                           neighbourhood=n,
                           neighbourhood_name=name,
                           merchants=merchants,
                           categories=categories,
                           all_neighbourhoods=NEIGHBOURHOODS,
                           lang=lang)


@public_bp.route('/merchant/<slug>/contact', methods=['POST'])
@limiter.limit("5 per hour")
def contact_merchant(slug):
    import re
    from utils.sanitise import clean_text
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True).first_or_404()

    sender_name  = clean_text(request.form.get('sender_name', ''))
    sender_email = clean_text(request.form.get('sender_email', ''))
    body         = clean_text(request.form.get('body', ''))

    if not sender_name or not sender_email or not body:
        flash('Veuillez remplir tous les champs. / Please fill in all fields.', 'error')
        return redirect(url_for('public.merchant_profile', slug=slug))

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', sender_email):
        flash('Invalid email address.', 'error')
        return redirect(url_for('public.merchant_profile', slug=slug))

    if len(body) > 2000:
        flash('Message too long.', 'error')
        return redirect(url_for('public.merchant_profile', slug=slug))

    msg = Message(
        merchant_id  = merchant.id,
        sender_name  = sender_name,
        sender_email = sender_email,
        body         = body,
    )
    db.session.add(msg)
    db.session.commit()

    try:
        from utils.mail import _send
        subject  = f"New message via Citify — {merchant.business_name}"
        body_txt = (
            f"You have received a new message via your Citify listing.\n\n"
            f"From: {sender_name} <{sender_email}>\n\n"
            f"Message:\n{body}\n\n"
            f"---\nReply directly to {sender_email} to respond.\n"
            f"This message was sent via citify.ca"
        )
        body_html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
          <h2 style="color:#e94560;">New Message via Citify</h2>
          <p><strong>From:</strong> {sender_name} &lt;{sender_email}&gt;</p>
          <p><strong>Listing:</strong> {merchant.business_name}</p>
          <div style="margin-top:16px;padding:16px;background:#f9fafb;border-radius:8px;
                      border-left:4px solid #e94560;font-size:15px;line-height:1.7;
                      white-space:pre-wrap;">{body}</div>
          <p style="font-size:13px;color:#9ca3af;margin-top:16px;">
            Reply directly to {sender_email} to respond.<br>
            Sent via citify.ca
          </p>
        </div>"""
        _send(to=merchant.email, subject=subject, body_text=body_txt, body_html=body_html)
    except Exception:
        pass

    flash('Message sent! / Message envoye!', 'success')
    return redirect(url_for('public.merchant_profile', slug=slug))

@public_bp.route('/advertise')
def advertise():
    lang = get_lang()
    categories = Category.query.all()
    return render_template('public/advertise.html', lang=lang, categories=categories)


@public_bp.route('/upgrade/autosync')
def upgrade_autosync():
    return redirect('https://learnwithleshley.gumroad.com/l/nutex')


@public_bp.route('/robots.txt')
def robots_txt():
    from flask import send_from_directory, current_app
    import os
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'robots.txt'
    ), 200, {'Content-Type': 'text/plain'}

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
                           categories=categories,
                           neighbourhoods=NEIGHBOURHOODS), 200, {'Content-Type': 'application/xml'}

@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    from utils.mail import _send
    lang = get_lang()
    success = False
    error   = False

    if request.method == 'POST':
        sender_name  = request.form.get('name', '').strip()
        sender_email = request.form.get('email', '').strip()
        subject_line = request.form.get('subject', '').strip()
        message      = request.form.get('message', '').strip()

        if sender_name and sender_email and subject_line and message:
            body_text = (
                f"New contact form submission from citify.ca\n\n"
                f"Name:    {sender_name}\n"
                f"Email:   {sender_email}\n"
                f"Subject: {subject_line}\n\n"
                f"Message:\n{message}\n\n"
                f"---\nReply directly to {sender_email} to respond."
            )
            body_html = f"""
            <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
              <h2 style="color:#e94560;">New Contact Form Submission — Citify</h2>
              <table style="width:100%;border-collapse:collapse;font-size:15px;">
                <tr><td style="padding:8px;font-weight:600;width:100px;">Name</td>
                    <td style="padding:8px;">{sender_name}</td></tr>
                <tr style="background:#f9fafb;">
                    <td style="padding:8px;font-weight:600;">Email</td>
                    <td style="padding:8px;"><a href="mailto:{sender_email}">{sender_email}</a></td></tr>
                <tr><td style="padding:8px;font-weight:600;">Subject</td>
                    <td style="padding:8px;">{subject_line}</td></tr>
              </table>
              <div style="margin-top:20px;padding:16px;background:#f9fafb;border-radius:8px;
                          border-left:4px solid #e94560;font-size:15px;line-height:1.7;
                          white-space:pre-wrap;">{message}</div>
              <p style="margin-top:20px;font-size:13px;color:#9ca3af;">
                Sent via citify.ca contact form
              </p>
            </div>"""

            ok = _send(
                to      = "ly22@protonmail.com",
                subject = f"[Citify Contact] {subject_line}",
                body_text = body_text,
                body_html = body_html
            )
            if ok:
                success = True
            else:
                error = True
        else:
            error = True

    return render_template('public/contact.html', lang=lang, success=success, error=error)

@public_bp.route('/merchant/<slug>/rate', methods=['POST'])
def rate_merchant(slug):
    merchant = Merchant.query.filter_by(slug=slug, is_active=True).first_or_404()
    ip = request.remote_addr
    try:
        score = int(request.form.get('score', 0))
    except (ValueError, TypeError):
        score = 0
    if score < 1 or score > 5:
        flash('Invalid rating.' , 'error')
        return redirect(url_for('public.merchant_profile', slug=slug))
    comment = request.form.get('comment', '').strip()[:300]

    # One rating per IP per merchant
    existing = Rating.query.filter_by(merchant_id=merchant.id, reviewer_ip=ip).first()
    if existing:
        existing.score   = score
        existing.comment = comment
    else:
        db.session.add(Rating(
            merchant_id = merchant.id,
            score       = score,
            comment     = comment,
            reviewer_ip = ip,
        ))
    db.session.flush()

    # Update cached avg + count on Merchant
    from sqlalchemy import func
    result = db.session.query(
        func.avg(Rating.score),
        func.count(Rating.id)
    ).filter(Rating.merchant_id == merchant.id).one()
    merchant.rating_avg   = round(float(result[0] or 0), 1)
    merchant.rating_count = result[1]
    db.session.commit()

    flash('Thank you for your rating! / Merci pour votre évaluation!', 'success')
    return redirect(url_for('public.merchant_profile', slug=slug) + '#ratings')


@public_bp.route('/favourites')
def favourites():
    lang = get_lang()
    return render_template('public/favourites.html', lang=lang)


@public_bp.route('/api/merchants/batch')
def merchants_batch():
    """Return basic merchant data for a list of IDs (used by favourites page)."""
    ids_raw = request.args.get('ids', '')
    try:
        ids = [int(i) for i in ids_raw.split(',') if i.strip().isdigit()][:50]
    except ValueError:
        ids = []
    if not ids:
        return jsonify([])
    merchants = Merchant.query.filter(
        Merchant.id.in_(ids), Merchant.is_active == True
    ).all()
    return jsonify([{
        'id':            m.id,
        'business_name': m.business_name,
        'slug':          m.slug,
        'logo_url':      m.logo_url or '',
        'neighbourhood': m.neighbourhood or '',
        'category':      m.category.name_en if m.category else '',
        'rating_avg':    m.rating_avg or 0,
        'rating_count':  m.rating_count or 0,
        'url':           url_for('public.merchant_profile', slug=m.slug),
    } for m in merchants])
