# scheduler_root.py
import os
import time
import random
import pickle
import psutil
from datetime import datetime
import pandas as pd
from models import Task, db, Log

# Import classical schedulers and Process from scheduling/scheduler.py
from scheduling.scheduler import (
    fcfs as fcfs_scheduler,
    sjf as sjf_scheduler,
    srtf as srtf_scheduler,
    priority_scheduling as priority_scheduler,
    round_robin as round_robin_scheduler,
    Process,
)

# =========================
# Optional ML model
# =========================
MODEL_PATH = "scheduler_model.pkl"
scheduler_model = None
if os.path.exists(MODEL_PATH):
    try:
        with open(MODEL_PATH, "rb") as f:
            scheduler_model = pickle.load(f)
        print("✅ Loaded ML scheduler model")
    except Exception as e:
        print(f"⚠️ Failed to load ML model: {e}")
        scheduler_model = None
else:
    print("⚠️ No ML model found, running in rule-only mode")

# ----------------------
# Load Priority Model
# ----------------------
priority_model = None
if os.path.exists("priority_model.pkl"):
    try:
        with open("priority_model.pkl", "rb") as f:
            priority_model = pickle.load(f)
        print("✅ Loaded Priority Assignment Model")
    except Exception as e:
        print(f"⚠️ Failed to load priority model: {e}")


def _system_snapshot():
    """Read battery/cpu/temp with safe fallbacks."""
    battery = psutil.sensors_battery()
    battery_level = battery.percent if battery else 50
    is_charging = battery.power_plugged if battery else False
    cpu = psutil.cpu_percent(interval=0.1)
    temp = 0
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # pick the first available sensor
            for _, entries in temps.items():
                if entries and getattr(entries[0], "current", None) is not None:
                    temp = entries[0].current
                    break
    except Exception:
        pass
    return battery_level, is_charging, cpu, temp


def _task_priority_value(task):
    """Map textual priority to numeric (lower is higher priority in scheduler)."""
    # Your generators use lower value = higher priority. Keep consistent:
    # We'll map High→0, Medium→1, Low→2
    mapping = {"High": 0, "Medium": 1, "Low": 2}
    return mapping.get(getattr(task, "priority", "Medium"), 1)


def _task_burst_time(task):
    """
    Derive a positive burst_time from your Task model.
    Prefer 'energy' or 'progress' if present, else default to 3.
    """
    # Ensure >= 1
    for attr in ("energy", "progress"):
        val = getattr(task, attr, None)
        if isinstance(val, (int, float)) and val > 0:
            return int(max(1, round(val)))
    return 3


def _make_processes_from_tasks(tasks):
    """
    Convert DB tasks (already classified as runnable) into Process objects
    with realistic arrival times and optional I/O events.
    """
    processes = []
    for t in tasks:
        burst = _task_burst_time(t)
        prio = _task_priority_value(t)

        # Arrival times: spread over a small window to show dynamics
        arrival_time = random.randint(0, min(5, max(0, burst // 2 + 1)))

        # I/O request times: choose a small random subset of execution points
        # Only pick times strictly within (0, burst) so they can trigger while running
        possible = list(range(1, max(1, burst)))
        io_count = 0
        if burst >= 4:
            # 30% chance to have 1 IO, 10% chance to have 2 IOs
            r = random.random()
            if r < 0.30:
                io_count = 1
            elif r < 0.40:
                io_count = 2
        io_times = set(random.sample(possible, k=min(io_count, len(possible)))) if possible else set()

        p = Process(
            pid=t.id,
            burst_time=burst,
            priority=prio,
            arrival_time=arrival_time,
            io_times=io_times,
        )
        processes.append(p)
    return processes


def run_scheduler_with_intelligence(algorithm, app, socketio):
    """
    Hybrid ML + Rule-based + Battery-aware scheduler driver.
    Picks an algorithm adaptively, emits updates each step,
    and simulates OS-like behavior via scheduling generators.
    """
    with app.app_context():
        tasks = Task.query.all()
        runnable, paused, batched, deferred, throttled = [], [], [], [], []

        # =====================
        # System snapshot
        # =====================
        battery_level, is_charging, cpu, temp = _system_snapshot()
        now = time.time()

        # =====================
        # Per-task decisioning
        # =====================
        for task in tasks:
            prio_val = _task_priority_value(task)  # 0 (High) / 1 (Medium) / 2 (Low)
            decision = "Run"  # default

            # 1) ML advisory (if present)
            if scheduler_model:
                try:
                    # NOTE: model feature order must match training; this is illustrative
                    features = pd.DataFrame(
                        [[battery_level, cpu, temp, prio_val]],
                        columns=["battery", "cpu", "temp", "priority"]
                    )
                    pred = scheduler_model.predict(features)[0]
                    decision = "Run" if int(pred) == 1 else "Pause"
                except Exception as e:
                    print("⚠️ ML decision failed:", e)

            # 2) Battery-aware overrides (apply when on battery only)
            if not is_charging:
                if battery_level > 50:
                    decision = "Run"
                elif 20 <= battery_level <= 50:
                    if prio_val == 0:       # High
                        decision = "Run"
                    elif prio_val == 1:     # Medium
                        decision = "Batch"
                    else:                   # Low
                        decision = "Defer"
                else:  # < 20%
                    if prio_val == 0:       # High
                        decision = "Run"
                    elif prio_val == 1:     # Medium
                        decision = "Throttle"
                    else:                   # Low
                        decision = "Pause"

            # 3) Deadline awareness (if your Task has 'deadline' as epoch seconds)
            if getattr(task, "deadline", None) and task.deadline < now + 10:
                decision = "Run"

            # 4) Assign state
            if decision == "Run":
                task.status = "Ready"
                runnable.append(task)
            elif decision == "Pause":
                task.status = "Paused"
                paused.append(task)
            elif decision == "Batch":
                task.status = "Batched"
                batched.append(task)
            elif decision == "Defer":
                task.status = "Deferred"
                deferred.append(task)
            elif decision == "Throttle":
                task.status = "Throttled"
                throttled.append(task)

            # Feedback/logging
            db.session.add(
                Log(
                    task_id=task.id,
                    decision=decision,
                    battery=battery_level,
                    cpu=cpu,
                    timestamp=datetime.now(),
                    outcome="pending",
                )
            )

        db.session.commit()

        # =====================
        # Convert Tasks → Processes
        # =====================
        processes = _make_processes_from_tasks(runnable)

        # If nothing runnable, keep UI informed and exit cleanly
        if not processes:
            socketio.emit(
                "update_algorithm",
                {"algorithm": "Idle (No runnable tasks)"},
                namespace="/",
            )
            socketio.emit(
                "scheduling_step",
                {
                    "running": None,
                    "queue": [],
                    "paused": [t.name for t in paused],
                    "batched": [t.name for t in batched],
                    "deferred": [t.name for t in deferred],
                    "throttled": [t.name for t in throttled],
                    "cpu": cpu,
                    "battery": battery_level,
                    "forecast": f"{battery_level}%",
                },
                namespace="/",
            )
            return

            # =====================
        # Charging Mode: Max Performance Allowed
        # =====================
        if is_charging:
            if cpu < 40:
                algo_name = "Shortest Remaining Time First (SRTF)"
                scheduler = srtf_scheduler(processes)
            elif 40 <= cpu < 70:
                algo_name = "Round Robin"
                scheduler = round_robin_scheduler(processes, quantum=2)
            else:
                algo_name = "Priority Scheduling"
                scheduler = priority_scheduler(processes)
            return algo_name, scheduler

        # =====================
        # High Battery & Light CPU Load
        # =====================
        elif battery_level > 50 and cpu < 50:
            algo_name = "Shortest Remaining Time First (SRTF)"
            scheduler = srtf_scheduler(processes)
            return algo_name, scheduler

        # =====================
        # Medium Battery (20–50%)
        # =====================
        elif 20 < battery_level <= 50:
            if cpu > 70:
                algo_name = "Priority Scheduling"
                scheduler = priority_scheduler(processes)
            else:
                algo_name = "Round Robin"
                scheduler = round_robin_scheduler(processes, quantum=3)
            return algo_name, scheduler

        # =====================
        # Low Battery Mode (≤20%)
        # =====================
        else:
            algo_name = "Priority Scheduling"
            scheduler = priority_scheduler(processes)
            return algo_name, scheduler

        # Let the frontend show the active algorithm
        socketio.emit("update_algorithm", {"algorithm": algo_name}, namespace="/")

        # =====================
        # Execute runnable tasks (step-by-step from generator)
        # =====================
        for step in scheduler:
            socketio.emit(
                "scheduling_step",
                {
                    "running": step.get("running"),
                    "queue": step.get("queue"),
                    "paused": [t.name for t in paused],
                    "batched": [t.name for t in batched],
                    "deferred": [t.name for t in deferred],
                    "throttled": [t.name for t in throttled],
                    "cpu": cpu,
                    "battery": battery_level,
                    "forecast": f"{battery_level}%",
                },
                namespace="/",
            )

            # Throttle effect: simulate slower progress when app decided to throttle medium-priority work
            time.sleep(1.5 if throttled else 0.5)

        # =====================
        # Mark completed in logs
        # =====================
        for task in runnable:
            log = (
                Log.query.filter_by(task_id=task.id)
                .order_by(Log.id.desc())
                .first()
            )
            if log:
                log.outcome = "completed"
        db.session.commit()
