# models.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    # Flaga: Czy użytkownik jest administratorem?
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), unique=True, nullable=False)
    sysname = db.Column(db.String(100), nullable=True)
    enabled = db.Column(db.Boolean, default=True)

    # Status ostatniego backupu (cache w bazie dla szybkości)
    last_backup_time = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(20), default="never")  # success, error, running
    last_error = db.Column(db.Text, nullable=True)


class BackupLog(db.Model):
    __tablename__ = 'backup_logs'
    id = db.Column(db.Integer, primary_key=True)
    device_ip = db.Column(db.String(45), nullable=False)  # IP jako klucz obcy logiczny
    filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20))  # success, error
    size_bytes = db.Column(db.Integer, default=0)

    # Czy plik jest zaszyfrowany?
    encrypted = db.Column(db.Boolean, default=True)

    # NOWE POLE: Kto uruchomił backup? 'cron' lub 'manual'
    trigger_type = db.Column(db.String(20), default='manual')


class Settings(db.Model):
    """Tabela na klucz-wartość dla ustawień (np. harmonogram)"""
    __tablename__ = 'settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))