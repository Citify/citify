from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from models import Merchant, Product, Flag
from app import db
from utils.lang import get_lang

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
    lang      = get_lang()
    page      = request.args.get('page', 1, type=int)
    merchants = Merchant.query.order_by(
        Merchant.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/merchants.html', merchants=merchants, lang=lang)


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
