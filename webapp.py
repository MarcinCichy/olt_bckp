# webapp.py
import click
import io
import threading
import zipfile
from pathlib import Path
from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from extensions import db, login_manager
from models import User, Device, BackupLog, Settings
from auth import auth_bp
from user_admin import user_admin_bp
from backup_service import BackupService
from log_viewer import get_logs_for_ip
import security_utils
import config
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object(config)

# Inicjalizacja rozszerzeń
db.init_app(app)
login_manager.init_app(app)

# Rejestracja Blueprintów
app.register_blueprint(auth_bp)
app.register_blueprint(user_admin_bp)

# Serwis backupu
backup_service = BackupService(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# === HELPERY DO USTAWIEŃ ===
def get_setting(key, default):
    setting = db.session.get(Settings, key)
    return setting.value if setting else default


def set_setting(key, value):
    setting = db.session.get(Settings, key)
    if not setting:
        setting = Settings(key=key, value=str(value))
        db.session.add(setting)
    else:
        setting.value = str(value)
    db.session.commit()


class ScheduleDTO:
    def __init__(self):
        self.enabled = (get_setting('schedule_enabled', '0') == '1')
        self.hour = int(get_setting('schedule_hour', '3'))
        self.minute = int(get_setting('schedule_minute', '0'))
        self.last_run_date = get_setting('schedule_last_run', None)


# === CLI COMMANDS ===
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Baza danych zainicjalizowana.")


@app.cli.command("update-schema")
def update_schema():
    """Ręczna aktualizacja schematu bazy (dodanie kolumn), jeśli używasz SQLite."""
    try:
        with app.app_context():
            if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
                with db.engine.connect() as conn:
                    # 1. Próba dodania is_admin
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                        print("Dodano kolumnę 'is_admin'.")
                    except Exception:
                        pass

                        # 2. Próba dodania trigger_type
                    try:
                        conn.execute(
                            text("ALTER TABLE backup_logs ADD COLUMN trigger_type VARCHAR(20) DEFAULT 'manual'"))
                        print("Dodano kolumnę 'trigger_type'.")
                    except Exception:
                        pass

                    conn.commit()
            else:
                print("Automatyczna aktualizacja dostępna tylko dla SQLite.")
    except Exception as e:
        print(f"Błąd aktualizacji schematu: {e}")


@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.option("--admin", is_flag=True, help="Utwórz użytkownika z uprawnieniami administratora")
def create_user(username, password, admin):
    db.create_all()
    if User.query.filter_by(username=username).first():
        print(f"Użytkownik {username} już istnieje.")
        return

    u = User(username=username, is_admin=admin)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    role = "ADMINA" if admin else "użytkownika"
    print(f"Utworzono {role}: {username}")


@app.cli.command("import-devices")
def import_devices():
    try:
        with open(config.DEVICES_FILE, 'r', encoding='utf-8') as f:
            ips = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        count = 0
        for ip in ips:
            if not Device.query.filter_by(ip=ip).first():
                d = Device(ip=ip, enabled=True)
                db.session.add(d)
                count += 1
        db.session.commit()
        print(f"Zaimportowano {count} nowych urządzeń.")
    except FileNotFoundError:
        print("Plik devices.txt nie istnieje.")


# === WIDOKI GŁÓWNE ===

@app.route("/")
@login_required
def index():
    devices = Device.query.all()
    thread_active = backup_service.is_running()
    any_device_running = any(d.last_status == 'running' for d in devices)
    should_refresh = thread_active or any_device_running

    schedule = ScheduleDTO()
    return render_template(
        "index.html",
        devices=devices,
        has_running=should_refresh,
        is_service_busy=thread_active,
        schedule=schedule
    )


@app.route("/backup/all", methods=["POST"])
@login_required
def backup_all():
    if backup_service.is_running():
        flash("Backup trwa...")
        return redirect(url_for('index'))

    t = threading.Thread(target=backup_service.backup_all_devices_thread)
    t.start()
    flash("Uruchomiono backup w tle.")
    return redirect(url_for('index'))


@app.route("/backup/selected", methods=["POST"])
@login_required
def backup_selected():
    if backup_service.is_running():
        flash("Backup trwa...")
        return redirect(url_for('index'))

    ips = request.form.getlist("device_ip")
    if not ips:
        flash("Nie wybrano żadnego urządzenia.")
        return redirect(url_for('index'))

    def worker():
        with app.app_context():
            # Ręczne uruchomienie z GUI zawsze jest 'manual'
            backup_service.backup_devices_logic(selected_ips=ips, trigger_type='manual')

    t = threading.Thread(target=worker)
    t.start()
    flash(f"Uruchomiono backup dla {len(ips)} urządzeń.")
    return redirect(url_for('index'))


@app.route("/backup/cancel", methods=["POST"])
@login_required
def backup_cancel():
    backup_service.request_cancel()
    flash("Wysłano żądanie anulowania.")
    return redirect(url_for("index"))


# === ZARZĄDZANIE URZĄDZENIAMI (NOWE) ===

@app.route("/device/add", methods=["POST"])
@login_required
def add_device():
    ip = request.form.get("ip", "").strip()
    if not ip:
        flash("Adres IP nie może być pusty.", "warning")
        return redirect(url_for('index'))

    if Device.query.filter_by(ip=ip).first():
        flash(f"Urządzenie {ip} już istnieje w bazie.", "warning")
        return redirect(url_for('index'))

    try:
        new_dev = Device(ip=ip, enabled=True)
        db.session.add(new_dev)
        db.session.commit()
        flash(f"Dodano urządzenie: {ip}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Błąd bazy danych: {e}", "danger")

    return redirect(url_for('index'))


@app.route("/device/delete/<int:dev_id>", methods=["POST"])
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

    return redirect(url_for('index'))


# === WIDOKI SZCZEGÓŁOWE ===

@app.route("/device/<int:dev_id>/details")
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


@app.route("/device/<int:dev_id>/logs")
@login_required
def device_logs(dev_id):
    return redirect(url_for('device_details', dev_id=dev_id))


@app.route("/device/<int:dev_id>/backups")
@login_required
def device_backups(dev_id):
    return redirect(url_for('device_details', dev_id=dev_id))


# ===============================================

@app.route("/backup/view/<int:log_id>")
@login_required
def view_backup(log_id):
    log = BackupLog.query.get_or_404(log_id)
    path = Path(config.BACKUP_DIR) / log.filename
    content = security_utils.decrypt_from_file(path)
    return render_template("view_backup.html", filename=log.filename, content=content)


@app.route("/backup/download/<int:log_id>")
@login_required
def download_backup(log_id):
    log = BackupLog.query.get_or_404(log_id)
    path = Path(config.BACKUP_DIR) / log.filename
    content = security_utils.decrypt_from_file(path)
    mem = io.BytesIO()
    mem.write(content.encode('utf-8'))
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name=log.filename,
        mimetype="text/plain"
    )


@app.route("/backup/delete/<int:log_id>", methods=["POST"])
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
    return redirect(request.referrer or url_for('index'))


@app.route("/schedule/update", methods=["POST"])
@login_required
def update_schedule():
    enabled = request.form.get("enabled") == "on"
    try:
        hour = int(request.form.get("hour", "3"))
        minute = int(request.form.get("minute", "0"))
    except ValueError:
        flash("Błędny format czasu.")
        return redirect(url_for("index"))

    set_setting('schedule_enabled', '1' if enabled else '0')
    set_setting('schedule_hour', str(hour))
    set_setting('schedule_minute', str(minute))
    flash("Zaktualizowano harmonogram.")
    return redirect(url_for('index'))


@app.route("/backups/latest")
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


@app.route("/backups/latest/download-all")
@login_required
def download_latest_backups_all():
    logs = BackupLog.query.filter_by(status='success').order_by(BackupLog.created_at.desc()).limit(500).all()
    if not logs:
        flash("Brak backupów do pobrania.")
        return redirect(url_for("show_latest_backups"))

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
                zf.writestr(log.filename, content)

    mem.seek(0)
    return send_file(
        mem,
        mimetype="application/zip",
        as_attachment=True,
        download_name="latest_backups.zip",
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)