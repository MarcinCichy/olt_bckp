# webapp.py
from datetime import datetime
import threading
import io
import zipfile

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    send_file,
    flash,
)

from backup_service import BackupService
from schedule import ScheduleRepository
from log_viewer import get_logs_for_ip
import config


app = Flask(__name__)
# W realnej instalacji zmień na losowy, silny sekret
app.secret_key = "bardzo-tajny-klucz-zmien-mnie"

backup_service = BackupService()
storage = backup_service.storage
schedule_repo = ScheduleRepository(config.SCHEDULE_FILE)


def _run_backup_async(ips):
    """
    Uruchamia backup dla podanej listy IP w osobnym wątku,
    żeby nie blokować żądania HTTP (strona od razu się odświeża).
    """

    def worker():
        backup_service.backup_devices(ips)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


@app.route("/")
def index():
    # Lista urządzeń z informacją o ostatnim backupie i statusie
    devices = backup_service.list_devices_status()
    schedule = schedule_repo.load()
    has_running = any(d.status == "running" for d in devices)
    return render_template(
        "index.html",
        devices=devices,
        schedule=schedule,
        has_running=has_running,
    )


@app.route("/backups/latest")
def show_latest_backups():
    backups = backup_service.get_latest_backups_all_devices()
    return render_template("latest_backups.html", backups=backups)


@app.route("/backups/latest/download-all")
def download_latest_backups_all():
    backups = backup_service.get_latest_backups_all_devices()
    if not backups:
        flash("Brak backupów do pobrania.")
        return redirect(url_for("show_latest_backups"))

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for b in backups:
            path = storage.get_backup_path(b.filename)
            zf.write(path, arcname=b.filename)

    mem.seek(0)
    return send_file(
        mem,
        mimetype="application/zip",
        as_attachment=True,
        download_name="latest_backups.zip",
    )


@app.route("/backup/all", methods=["POST"])
def backup_all():
    # Backup wszystkich urządzeń w tle
    ips = backup_service.list_devices()
    if not ips:
        flash("Brak urządzeń w pliku. Nie można uruchomić backupu.")
        return redirect(url_for("index"))

    now_str = datetime.now().isoformat(timespec="seconds")
    for ip in ips:
        backup_service.status_repo.set_running(ip, now_str)

    _run_backup_async(ips)

    flash("Backup wszystkich urządzeń został uruchomiony w tle.")
    return redirect(url_for("index"))


@app.route("/backup/selected", methods=["POST"])
def backup_selected():
    ips = request.form.getlist("device_ip")
    if not ips:
        flash("Nie wybrano żadnego urządzenia.")
        return redirect(url_for("index"))

    now_str = datetime.now().isoformat(timespec="seconds")
    for ip in ips:
        backup_service.status_repo.set_running(ip, now_str)

    _run_backup_async(ips)

    flash("Backup wybranych urządzeń został uruchomiony w tle.")
    return redirect(url_for("index"))


@app.route("/device/<ip>/backups")
def device_backups(ip):
    backups = storage.list_backups(ip=ip)
    return render_template("device_backups.html", ip=ip, backups=backups)


@app.route("/device/<ip>/logs")
def device_logs(ip):
    """
    Podgląd logów związanych z danym IP oraz ostatniego statusu backupu.
    """
    state = backup_service.status_repo.get_record(ip)
    log_lines = get_logs_for_ip(ip, max_lines=200)
    return render_template("device_logs.html", ip=ip, state=state, log_lines=log_lines)


@app.route("/backup/view/<filename>")
def view_backup(filename):
    try:
        content = storage.read_backup(filename)
    except FileNotFoundError:
        flash("Plik backupu nie istnieje.")
        return redirect(url_for("index"))
    return render_template("view_backup.html", filename=filename, content=content)


@app.route("/backup/delete/<filename>", methods=["POST"])
def delete_backup(filename):
    deleted = storage.delete_backup(filename)
    if deleted:
        flash(f"Backup {filename} został usunięty.")
    else:
        flash(f"Backup {filename} nie istnieje.")
    ref = request.referrer or url_for("index")
    return redirect(ref)


@app.route("/backup/download/<filename>")
def download_backup(filename):
    return send_from_directory(
        storage.backup_dir,
        filename,
        as_attachment=True,
        download_name=filename,
    )


@app.route("/schedule/update", methods=["POST"])
def update_schedule():
    enabled = request.form.get("enabled") == "on"
    try:
        hour = int(request.form.get("hour", "3"))
        minute = int(request.form.get("minute", "0"))
    except ValueError:
        flash("Nieprawidłowy format godziny lub minut.")
        return redirect(url_for("index"))

    schedule = schedule_repo.load()
    schedule.enabled = enabled
    schedule.hour = hour
    schedule.minute = minute
    schedule_repo.save(schedule)

    flash("Zaktualizowano harmonogram backupu.")
    return redirect(url_for("index"))


def create_app():
    """
    Funkcja pomocnicza, jeśli będziesz chciał uruchamiać aplikację
    przez gunicorn/uwsgi itp.
    """
    return app


if __name__ == "__main__":
    # Uruchomienie lokalne: python webapp.py
    app.run(host="0.0.0.0", port=5000, debug=True)
