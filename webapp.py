# webapp.py
import click
from flask import Flask, request
from sqlalchemy import text

# Importy lokalne
import config
from extensions import db, login_manager
from models import User, Device, Settings, BackupLog

# Importy modułów (Blueprintów)
from routes.auth_bp import auth_bp
from routes.user_admin_bp import user_admin_bp
from routes.main_bp import main_bp
from routes.device_bp import device_bp
from routes.backup_bp import backup_bp
from routes.settings_bp import settings_bp

# Import serwisu backupu (instancja)
from services import backup_service

app = Flask(__name__)
app.config.from_object(config)

# Inicjalizacja rozszerzeń
db.init_app(app)
login_manager.init_app(app)

# Rejestracja Blueprintów
app.register_blueprint(auth_bp)
app.register_blueprint(user_admin_bp)
app.register_blueprint(main_bp)
app.register_blueprint(device_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(settings_bp)

# Inicjalizacja serwisu backupu (przypisanie app)
backup_service.init_app(app)


# === FILTR DO KOLOROWANIA LOGÓW (POPRAWIONY) ===
@app.template_filter('colorize_log')
def colorize_log(line):
    if not line:
        return ""

    # 1. Usuwamy białe znaki z początku i końca (kluczowe dla usunięcia podwójnych enterów)
    line = line.strip()

    # 2. Jeśli po usunięciu spacji linia jest pusta, ignorujemy ją
    if not line:
        return ""

    # 3. Nadajemy kolory
    if "ERROR" in line or "CRITICAL" in line or "FAIL" in line:
        return f'<span style="color: #ff5f5f;">{line}</span>'  # Czerwony
    elif "WARNING" in line:
        return f'<span style="color: #ffcc00;">{line}</span>'  # Żółty
    elif "INFO" in line:
        return f'<span style="color: #2ecc71;">{line}</span>'  # Zielony
    elif "DEBUG" in line:
        return f'<span style="color: #3498db;">{line}</span>'  # Niebieski
    else:
        return f'<span style="color: #cccccc;">{line}</span>'  # Szary


# === FIX: Blokada przycisku WSTECZ po wylogowaniu ===
@app.after_request
def add_header(response):
    """
    Dodaje nagłówki zabraniające przeglądarce zapisywania stron w cache.
    """
    if request.path.startswith('/static'):
        return response

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# === CLI COMMANDS ===
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Baza danych zainicjalizowana.")


@app.cli.command("update-schema")
def update_schema():
    try:
        with app.app_context():
            if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    except Exception:
                        pass
                    try:
                        conn.execute(
                            text("ALTER TABLE backup_logs ADD COLUMN trigger_type VARCHAR(20) DEFAULT 'manual'"))
                    except Exception:
                        pass
                    conn.commit()
            else:
                print("Update schema only for SQLite.")
    except Exception as e:
        print(f"Error: {e}")


@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.option("--admin", is_flag=True)
def create_user(username, password, admin):
    db.create_all()
    if User.query.filter_by(username=username).first():
        print(f"Użytkownik {username} już istnieje.")
        return
    u = User(username=username, is_admin=admin)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    print(f"Utworzono użytkownika: {username}")


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


@app.cli.command("reset-stuck")
def reset_stuck_command():
    """Ręczne resetowanie zawieszonych statusów (klepsydry)."""
    reset_stuck_backups()
    print("Zakończono resetowanie statusów.")


# === FUNKCJA NAPRAWCZA (SYSTEM CLEANUP) ===
def reset_stuck_backups():
    """
    Funkcja uruchamiana przy starcie. Sprawdza, czy w bazie są urządzenia
    z ustawionym statusem 'running'. Jeśli tak - zmienia ich status na 'error'.
    """
    try:
        with app.app_context():
            stuck_devices = Device.query.filter_by(last_status='running').all()
            if stuck_devices:
                print(f" ---> [SYSTEM] Wykryto {len(stuck_devices)} przerwanych zadań backupu. Resetowanie statusów...")
                for d in stuck_devices:
                    d.last_status = 'error'
                    d.last_error = "Proces przerwany (restart aplikacji)"
                db.session.commit()
                print(" ---> [SYSTEM] Statusy naprawione.")
    except Exception as e:
        print(f" ---> [SYSTEM] Błąd podczas czyszczenia statusów: {e}")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # Wywołanie czyszczenia "zombie" statusów przed startem serwera
    reset_stuck_backups()

    app.run(host="0.0.0.0", port=5000, debug=True)