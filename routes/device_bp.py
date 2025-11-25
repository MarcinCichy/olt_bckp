from flask import Blueprint, request, flash, redirect, url_for, render_template
from flask_login import login_required
from extensions import db
from models import Device, BackupLog
from log_viewer import get_logs_for_ip

device_bp = Blueprint('device', __name__)

@device_bp.route("/device/add", methods=["POST"])
@login_required
def add_device():
    ip = request.form.get("ip", "").strip()
    if not ip:
        flash("Adres IP nie może być pusty.", "warning")
        return redirect(url_for('main.index')) # POPRAWKA

    if Device.query.filter_by(ip=ip).first():
        flash(f"Urządzenie {ip} już istnieje w bazie.", "warning")
        return redirect(url_for('main.index')) # POPRAWKA

    try:
        new_dev = Device(ip=ip, enabled=True)
        db.session.add(new_dev)
        db.session.commit()
        flash(f"Dodano urządzenie: {ip}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Błąd bazy danych: {e}", "danger")

    return redirect(url_for('main.index')) # POPRAWKA


@device_bp.route("/device/delete/<int:dev_id>", methods=["POST"])
@login_required
def delete_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    ip = dev.ip
    try:
        db.session.delete(dev)
        db.session.commit()
        flash(f"Usunięto urządzenie: {ip}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Błąd usuwania: {e}", "danger")

    return redirect(url_for('main.index')) # POPRAWKA


@device_bp.route("/device/<int:dev_id>/details")
@login_required
def device_details(dev_id):
    dev = Device.query.get_or_404(dev_id)
    db_logs = BackupLog.query.filter_by(device_ip=dev.ip).order_by(BackupLog.created_at.desc()).limit(50).all()
    text_logs = get_logs_for_ip(dev.ip, max_lines=100)

    return render_template(
        "device_details.html",
        device=dev,
        db_logs=db_logs,
        text_logs=text_logs
    )

# Aliasy
@device_bp.route("/device/<int:dev_id>/logs")
@login_required
def device_logs(dev_id):
    return redirect(url_for('device.device_details', dev_id=dev_id)) # POPRAWKA

@device_bp.route("/device/<int:dev_id>/backups")
@login_required
def device_backups(dev_id):
    return redirect(url_for('device.device_details', dev_id=dev_id)) # POPRAWKA