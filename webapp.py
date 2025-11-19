# webapp.py
import io
import threading
import zipfile
from datetime import datetime

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
app.secret_key = config.SECRET_KEY

# Singleton serwisu
backup_service = BackupService()
storage = backup_service.storage
schedule_repo = ScheduleRepository(config.SCHEDULE_FILE)


def _run_backup_async(ips):
    """Uruchamia backup w tle, o ile serwis jest wolny."""
    if backup_service.is_running():
        return False

    def worker():
        backup_service.backup_devices(ips)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


@app.route("/")
def index():
    devices = backup_service.list_devices_status()
    schedule = schedule_repo.load()

    # Sprawdzamy statusy, żeby wiedzieć czy odświeżać stronę
    is_busy = backup_service.is_running()
    has_running_status = any(d.status == "running" for d in devices)

    return render_template(
        "index.html",
        devices=devices,
        schedule=schedule,
        has_running=(is_busy or has_running_status),
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
            if path.is_file():
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
    if backup_service.is_running():
        flash("Backup jest już w toku.")
        return redirect(url_for("index"))

    ips = backup_service.list_devices()
    if not ips:
        flash("Brak urządzeń na liście.")
        return redirect(url_for("index"))

    if _run_backup_async(ips):
        flash("Rozpoczęto backup wszystkich urządzeń.")
    else:
        flash("Błąd uruchamiania (serwis zajęty).")

    return redirect(url_for("index"))


@app.route("/backup/selected", methods=["POST"])
def backup_selected():
    if backup_service.is_running():
        flash("Backup jest już w toku.")
        return redirect(url_for("index"))

    ips = request.form.getlist("device_ip")
    if not ips:
        flash("Nie wybrano żadnego urządzenia.")
        return redirect(url_for("index"))

    if _run_backup_async(ips):
        flash(f"Rozpoczęto backup {len(ips)} wybranych urządzeń.")
    else:
        flash("Błąd uruchamiania (serwis zajęty).")

    return redirect(url_for("index"))


@app.route("/backup/cancel", methods=["POST"])
def backup_cancel():
    backup_service.request_cancel()
    flash("Wysłano żądanie anulowania.")
    return redirect(url_for("index"))


@app.route("/device/<ip>/backups")
def device_backups(ip):
    backups = storage.list_backups(ip=ip)
    return render_template("device_backups.html", ip=ip, backups=backups)


@app.route("/device/<ip>/logs")
def device_logs(ip):
    state = backup_service.status_repo.get_record(ip)
    log_lines = get_logs_for_ip(ip)
    return render_template("device_logs.html", ip=ip, state=state, log_lines=log_lines)


@app.route("/backup/view/<filename>")
def view_backup(filename):
    try:
        content = storage.read_backup(filename)
    except FileNotFoundError:
        flash("Plik nie istnieje.")
        return redirect(url_for("index"))
    return render_template("view_backup.html", filename=filename, content=content)


@app.route("/backup/delete/<filename>", methods=["POST"])
def delete_backup(filename):
    if storage.delete_backup(filename):
        flash(f"Usunięto plik {filename}.")
    else:
        flash("Plik nie istnieje lub nie można go usunąć.")
    return redirect(request.referrer or url_for("index"))


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
        flash("Błędny format czasu.")
        return redirect(url_for("index"))

    schedule = schedule_repo.load()
    schedule.enabled = enabled
    schedule.hour = hour
    schedule.minute = minute
    schedule_repo.save(schedule)

    flash("Zaktualizowano harmonogram.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)