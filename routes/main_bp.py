from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
from models import Device
from services import backup_service
from schedule import ScheduleService

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
@login_required
def index():
    devices = Device.query.all()
    thread_active = backup_service.is_running()
    any_device_running = any(d.last_status == 'running' for d in devices)
    should_refresh = thread_active or any_device_running

    schedule = ScheduleService.load_schedule()

    return render_template(
        "index.html",
        devices=devices,
        has_running=should_refresh,
        is_service_busy=thread_active,
        schedule=schedule
    )