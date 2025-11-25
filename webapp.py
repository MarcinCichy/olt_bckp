# webapp.py
import click
from flask import Flask
from sqlalchemy import text

# Importy lokalne
import config
from extensions import db, login_manager
from models import User, Device, Settings, BackupLog

# Importy modułów (Blueprintów)
from auth import auth_bp
from user_admin import user_admin_bp
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


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# === CLI COMMANDS (Baza, Userzy, Import) ===
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Baza danych zainicjalizowana.")

@app.cli.command("update-schema")
def update_schema():
    """Ręczna aktualizacja schematu dla SQLite."""
    try:
        with app.app_context():
            if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
                with db.engine.connect() as conn:
                    # Sprawdzamy i dodajemy kolumny jeśli ich brak
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                        print("Dodano kolumnę 'is_admin'.")
                    except Exception:
                        pass
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
@click.option("--admin", is_flag=True, help="Administrator")
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)