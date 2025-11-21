# user_admin.py
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import User
from extensions import db

user_admin_bp = Blueprint('user_admin', __name__)


def admin_required(f):
    """Dekorator sprawdzający, czy user ma flagę is_admin."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Brak uprawnień dostępu do tej sekcji.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


@user_admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    users = User.query.all()
    return render_template('users.html', users=users)


@user_admin_bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin_val = request.form.get('is_admin') == 'on'  # Checkbox zwraca 'on' jeśli zaznaczony

    if not username or not password:
        flash('Nazwa użytkownika i hasło są wymagane.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    if User.query.filter_by(username=username).first():
        flash('Użytkownik o takiej nazwie już istnieje.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    new_user = User(username=username, is_admin=is_admin_val)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    role_msg = "Administratora" if is_admin_val else "Użytkownika"
    flash(f'Utworzono {role_msg}: {username}.', 'success')
    return redirect(url_for('user_admin.list_users'))


@user_admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        flash('Nie znaleziono użytkownika.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    if user.id == current_user.id:
        flash('Nie możesz usunąć własnego konta, gdy jesteś zalogowany.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Usunięto użytkownika {user.username}.', 'info')
    return redirect(url_for('user_admin.list_users'))


@user_admin_bp.route('/users/reset-password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = db.session.get(User, user_id)
    new_password = request.form.get('new_password')

    if not user:
        flash('Nie znaleziono użytkownika.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    if not new_password:
        flash('Podaj nowe hasło.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    user.set_password(new_password)
    db.session.commit()

    flash(f'Zmieniono hasło dla użytkownika {user.username}.', 'success')
    return redirect(url_for('user_admin.list_users'))


@user_admin_bp.route('/users/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """Opcjonalnie: Przełączanie uprawnień admina istniejącemu userowi"""
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('user_admin.list_users'))

    if user.id == current_user.id:
        flash('Nie możesz odebrać sobie uprawnień admina.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    user.is_admin = not user.is_admin
    db.session.commit()

    status = "nadano" if user.is_admin else "odebrano"
    flash(f'Uprawnienia admina {status} dla {user.username}.', 'success')
    return redirect(url_for('user_admin.list_users'))