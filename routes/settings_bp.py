from flask import Blueprint, request, flash, redirect, url_for
from flask_login import login_required
from schedule import ScheduleService

settings_bp = Blueprint('settings', __name__)


@settings_bp.route("/schedule/update", methods=["POST"])
@login_required
def update_schedule():
    enabled = request.form.get("enabled") == "on"
    try:
        hour = int(request.form.get("hour", "3"))
        minute = int(request.form.get("minute", "0"))
    except ValueError:
        flash("Błędny format czasu.")
        return redirect(url_for("main.index"))

    # Load, update, save
    current_schedule = ScheduleService.load_schedule()
    current_schedule.enabled = enabled
    current_schedule.hour = hour
    current_schedule.minute = minute

    ScheduleService.save_schedule(current_schedule)

    flash("Zaktualizowano harmonogram.")
    return redirect(url_for('main.index'))