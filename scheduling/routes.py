from flask import Blueprint
from threading import Thread
import psutil
import random
import time
from models import Task, db

scheduling_bp = Blueprint("scheduling_bp", __name__)

@scheduling_bp.record_once
def register_socketio(state):
    socketio = state.app.extensions['socketio']

    @socketio.on("start_scheduling")
    def handle_start_scheduling(data):
        def run_simulation():
            with state.app.app_context():
                tasks = Task.query.filter_by(type='simulated').all()
                if not tasks:
                    socketio.emit("scheduling_update", {
                        "running": None,
                        "queue": [],
                        "cpu": 0,
                        "battery": 0,
                        "progress": {},
                        "forecastText": "N/A",
                        "forecastPercent": 0
                    })
                    return

                # Prepare process list
                processes = []
                priority_map = {"High": 1, "Medium": 2, "Low": 3}
                for t in tasks:
                    burst = getattr(t, "burst", len(t.name) % 5 + 1)
                    prio = priority_map.get(getattr(t, "priority", None), 2)
                    processes.append({"name": t.name, "burst": burst, "priority": prio})

                progress = {p["name"]: 0 for p in processes}

                def all_done():
                    return all(v >= 100 for v in progress.values())

                while not all_done():
                    # Read system stats
                    battery = psutil.sensors_battery()
                    battery_level = battery.percent if battery else random.randint(40, 100)
                    plugged_in = battery.power_plugged if battery else False
                    on_battery = not plugged_in
                    cpu_usage = int(psutil.cpu_percent())

                    # -------- Battery Forecast Calculation --------
                    if battery:
                        if battery.power_plugged:
                            forecast_text = "∞ (Charging)"
                            forecast_percent = 100
                        else:
                            if battery.secsleft == psutil.POWER_TIME_UNLIMITED:
                                forecast_text = "∞ (Idle)"
                                forecast_percent = 100
                            elif battery.secsleft == psutil.POWER_TIME_UNKNOWN:
                                forecast_text = "Unknown"
                                forecast_percent = 0
                            else:
                                est_minutes = battery.secsleft // 60
                                forecast_text = f"{est_minutes} min"
                                # map 0–120 minutes into 0–100% ring
                                forecast_percent = min(100, int((est_minutes / 120) * 100))
                    else:
                        forecast_text = "N/A"
                        forecast_percent = 0

                    # -------- Decide scheduling order --------
                    if not on_battery or battery_level > 70:
                        proc_list = sorted(processes, key=lambda x: x["burst"])  # SJF-like
                    elif battery_level > 40:
                        high = [p for p in processes if p["priority"] == 1]
                        medium_low = [p for p in processes if p["priority"] > 1]
                        proc_list = high + medium_low
                    else:
                        proc_list = sorted(processes, key=lambda x: x["priority"])

                    for p in proc_list:
                        name = p["name"]
                        if progress[name] >= 100:
                            continue

                        # skip low-priority tasks when battery is critical
                        if on_battery and battery_level < 40 and p["priority"] > 1:
                            continue

                        # --- Update progress ---
                        increment = max(1, int(100 / max(1, p["burst"])))
                        increment = min(increment, 20)
                        progress[name] = min(100, progress[name] + increment)

                        # Update DB
                        task = Task.query.filter_by(name=name).first()
                        if task:
                            task.progress = progress[name]
                            task.energy = min(100, progress[name] + 5)
                            task.status = "Completed" if task.progress >= 100 else "In Progress"
                            db.session.commit()

                        queue = [n for n, pct in progress.items() if pct < 100]

                        # Emit update (always includes forecast)
                        socketio.emit("scheduling_update", {
                            "running": name,
                            "queue": queue,
                            "cpu": cpu_usage,
                            "battery": battery_level,
                            "progress": progress,
                            "forecastText": forecast_text,
                            "forecastPercent": forecast_percent
                        })

                        time.sleep(1)

                    time.sleep(0.1)

                # -------- Final emit --------
                socketio.emit("scheduling_update", {
                    "running": None,
                    "queue": [],
                    "cpu": 0,
                    "battery": battery_level,
                    "progress": progress,
                    "forecastText": forecast_text,
                    "forecastPercent": forecast_percent
                })

        Thread(target=run_simulation, daemon=True).start()
