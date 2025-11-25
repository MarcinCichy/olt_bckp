from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import User
from extensions import db

user_admin_bp = Blueprint('user_admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Brak uprawnień dostępu do tej sekcji.", "danger")
            return redirect(url_for('main.index')) # POPRAWKA
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
    confirm_password = request.form.get('confirm_password')
    is_admin_val = request.form.get('is_admin') == 'on'

    if not username or not password or not confirm_password:
        flash('Wszystkie pola są wymagane.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    if password != confirm_password:
        flash('Podane hasła nie są identyczne.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    if User.query.filter_by(username=username).first():
        flash('Użytkownik o takiej nazwie już istnieje.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    new_user = User(username=username, is_admin=is_admin_val)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    flash(f'Utworzono użytkownika: {username}.', 'success')
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
        flash('Nie możesz usunąć własnego konta.', 'danger')
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
    confirm_password = request.form.get('confirm_password')

    if not user or not new_password or not confirm_password:
        flash('Błąd danych.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    if new_password != confirm_password:
        flash('Hasła nie są identyczne.', 'danger')
        return redirect(url_for('user_admin.list_users'))

    user.set_password(new_password)
    db.session.commit()

    flash(f'Zmieniono hasło dla {user.username}.', 'success')
    return redirect(url_for('user_admin.list_users'))

@user_admin_bp.route('/users/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('user_admin.list_users'))

    if user.id == current_user.id:
        flash('Nie możesz odebrać sobie uprawnień admina.', 'warning')
        return redirect(url_for('user_admin.list_users'))

    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f'Zmieniono uprawnienia dla {user.username}.', 'success')
    return redirect(url_for('user_admin.list_users'))