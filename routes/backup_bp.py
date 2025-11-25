import io
import threading
import zipfile
from pathlib import Path
from flask import Blueprint, request, flash, redirect, url_for, render_template, send_file, current_app
from flask_login import login_required

from extensions import db
from models import BackupLog
from services import backup_service
import config
import security_utils

backup_bp = Blueprint('backup', __name__)

@backup_bp.route("/backup/all", methods=["POST"])
@login_required
def backup_all():
    if backup_service.is_running():
        flash("Backup trwa...")
        return redirect(url_for('main.index'))

    t = threading.Thread(target=backup_service.backup_all_devices_thread)
    t.start()
    flash("Uruchomiono backup w tle.")
    return redirect(url_for('main.index'))


@backup_bp.route("/backup/selected", methods=["POST"])
@login_required
def backup_selected():
    if backup_service.is_running():
        flash("Backup trwa...")
        return redirect(url_for('main.index'))

    ips = request.form.getlist("device_ip")
    if not ips:
        flash("Nie wybrano żadnego urządzenia.")
        return redirect(url_for('main.index'))

    # Pobieramy realną aplikację (proxy), żeby przekazać ją do wątku
    app = current_app._get_current_object()

    def worker(app_obj, selected_ips):
        with app_obj.app_context():
            backup_service.backup_devices_logic(selected_ips=selected_ips, trigger_type='manual')

    t = threading.Thread(target=worker, args=(app, ips))
    t.start()
    flash(f"Uruchomiono backup dla {len(ips)} urządzeń.")
    return redirect(url_for('main.index'))


@backup_bp.route("/backup/cancel", methods=["POST"])
@login_required
def backup_cancel():
    backup_service.request_cancel()
    flash("Wysłano żądanie anulowania.")
    return redirect(url_for("main.index"))


@backup_bp.route("/backup/view/<int:log_id>")
@login_required
def view_backup(log_id):
    log = BackupLog.query.get_or_404(log_id)
    path = Path(config.BACKUP_DIR) / log.filename
    content = security_utils.decrypt_from_file(path)
    return render_template("view_backup.html", filename=log.filename, content=content)


@backup_bp.route("/backup/download/<int:log_id>")
@login_required
def download_backup(log_id):
    log = BackupLog.query.get_or_404(log_id)
    path = Path(config.BACKUP_DIR) / log.filename
    content = security_utils.decrypt_from_file(path)
    mem = io.BytesIO()
    mem.write(content.encode('utf-8'))
    mem.seek(0)

    dl_name = log.filename if log.filename.endswith('.txt') else f"{log.filename}.txt"

    return send_file(
        mem,
        as_attachment=True,
        download_name=dl_name,
        mimetype="text/plain"
    )


@backup_bp.route("/backup/delete/<int:log_id>", methods=["POST"])
@login_required
def delete_backup(log_id):
    log = BackupLog.query.get_or_404(log_id)
    path = Path(config.BACKUP_DIR) / log.filename
    try:
        if path.exists():
            path.unlink()
        db.session.delete(log)
        db.session.commit()
        flash(f"Usunięto backup {log.filename}")
    except Exception as e:
        flash(f"Błąd usuwania: {e}")
    return redirect(request.referrer or url_for('main.index'))


@backup_bp.route("/backups/latest")
@login_required
def show_latest_backups():
    logs = BackupLog.query.filter_by(status='success').order_by(BackupLog.created_at.desc()).limit(500).all()
    unique_backups = []
    seen_ips = set()
    for log in logs:
        if log.device_ip not in seen_ips:
            unique_backups.append(log)
            seen_ips.add(log.device_ip)
    return render_template("latest_backups.html", backups=unique_backups)


@backup_bp.route("/backups/latest/download-all")
@login_required
def download_latest_backups_all():
    logs = BackupLog.query.filter_by(status='success').order_by(BackupLog.created_at.desc()).limit(500).all()
    if not logs:
        flash("Brak backupów do pobrania.")
        return redirect(url_for("backup.show_latest_backups"))

    seen_ips = set()
    unique_logs = []
    for log in logs:
        if log.device_ip not in seen_ips:
            unique_logs.append(log)
            seen_ips.add(log.device_ip)

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for log in unique_logs:
            path = Path(config.BACKUP_DIR) / log.filename
            if path.exists():
                content = security_utils.decrypt_from_file(path)
                arcname = log.filename if log.filename.endswith('.txt') else f"{log.filename}.txt"
                zf.writestr(arcname, content)

    mem.seek(0)
    return send_file(
        mem,
        mimetype="application/zip",
        as_attachment=True,
        download_name="latest_backups.zip",
    )