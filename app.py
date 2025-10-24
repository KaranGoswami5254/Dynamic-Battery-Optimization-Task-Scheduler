import eventlet
eventlet.monkey_patch()
from datetime import datetime
from threading import Thread
import psutil
import importlib
import random
import time
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO,emit
from flask import request, redirect, url_for, flash
from config import Config
from models import db, Task, Log
from scheduling.routes import scheduling_bp
from scheduler_root import run_scheduler_with_intelligence,priority_model
import threading
from collections import defaultdict
from scheduling.scheduler_analytics import scheduler_analytics_bp
import math
app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB
db.init_app(app)

# Initialize Socket.IO
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Global thresholds
USER_THRESHOLDS = {'battery_low': 25, 'cpu_high': 85, 'temp_high': 75}

# Scheduler control
CURRENT_SCHEDULER = "Detecting...."
scheduler_thread = None

# Global temperature variable (with default value)
current_temperature = 45.0

start_scheduler = lambda: socketio.start_background_task(
    run_scheduler_with_intelligence, CURRENT_SCHEDULER, app, socketio
)
app.register_blueprint(scheduler_analytics_bp)
# ============================
# SIMPLE TEMPERATURE MONITORING
# ============================
def get_temperature_simple():
    """Simple temperature reading using psutil"""
    try:
        # Try psutil first (works on Windows 10/11)
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current is not None and entry.current > 0:
                            print(f"Found temperature sensor: {name} = {entry.current}°C")
                            return round(entry.current, 1)
        return None
    except Exception as e:
        print(f"psutil temperature error: {e}")
        return None

def get_temperature_estimated():
    """Estimate temperature based on CPU usage (always works)"""
    try:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        # Realistic temperature estimation formula
        base_temp = 35.0  # Base temperature when idle
        temp_factor = 0.4  # Temperature increase per CPU percentage
        
        estimated_temp = base_temp + (cpu_usage * temp_factor)
        
        # Add small random variation to make it look real (±2°C)
        variation = random.uniform(-2.0, 2.0)
        estimated_temp += variation
        
        # Keep within realistic bounds (30°C to 95°C)
        estimated_temp = max(30, min(estimated_temp, 95))
        
        return round(estimated_temp, 1)
    except Exception as e:
        print(f"Temperature estimation error: {e}")
        return 45.0  # Fallback value

def start_temperature_monitoring():
    """Simple temperature monitoring without console spam"""
    global current_temperature
    
    def temperature_loop():
        while True:
            # Try psutil first, fall back to estimation
            temp = get_temperature_simple() or get_temperature_estimated()
            
            if temp is not None:
                current_temperature = temp
                socketio.emit("temperature_update", {"temperature": temp})
            
            socketio.sleep(3)  # Update every 3 seconds
    
    eventlet.spawn(temperature_loop)

def calculate_battery_impact(tasks, algorithm, current_battery):
    """
    Estimate battery consumed by the current algorithm for all registered tasks.
    """
    if not tasks:
        return current_battery, 0

    total_energy_required = sum(task.energy for task in tasks)

    algo_factor = {
        "Round Robin": 1.0,
        "Priority Scheduling": 1.2,
        "Shortest Remaining Time First (SRTF)": 1.1
    }.get(algorithm, 1.0)

    estimated_consumed = total_energy_required * algo_factor

    battery_left = max(0, current_battery - estimated_consumed)
    battery_used = current_battery - battery_left

    return round(battery_left, 1), round(battery_used, 1)

# ============================
# Scheduler Simulation & Battery Forecast
# ============================

def run_scheduler_with_intelligence(socketio, algorithm, app):
    """
    Simulates task execution and emits progress to frontend.
    """
    with app.app_context():
        simulated_tasks = Task.query.filter_by(type='simulated').all()

        for task in simulated_tasks:
            if task.status == "Completed":
                continue

            task.status = "In Progress"
            db.session.commit()

            total_energy = random.randint(50, 100)
            energy_used = 0
            last_emit_progress = 0

            while energy_used < total_energy:
                socketio.sleep(0.5)  # smoother updates
                energy_used += random.randint(5, 10)
                progress = min(int((energy_used / total_energy) * 100), 100)

                # Emit only if progress increased by 5% or complete
                if progress - last_emit_progress >= 5 or progress == 100:
                    task.progress = progress
                    db.session.commit()
                    socketio.emit("task_progress_update", {
                        "task_id": task.id,
                        "progress": progress,
                        "status": "In Progress",
                        "type": "simulated"
                    })
                    last_emit_progress = progress

            task.progress = 100
            task.status = "Completed"
            task.locked = True
            db.session.commit()
            socketio.emit("task_progress_update", {
                "task_id": task.id,
                "progress": 100,
                "status": "Completed",
                "type": "simulated"
            })


def emit_battery_impact_incremental(socketio, algorithm, app):
    """
    Continuously calculates and emits battery forecast and algorithm impact.
    """
    import psutil
    from models import Task  # make sure your Task model is imported

    # To track battery history for estimating discharge rate
    battery_history = []

    algo_factors = {
        "Round Robin": 1.0,
        "Priority Scheduling": 1.2,
        "Shortest Remaining Time First (SRTF)": 1.1,
        "FCFS": 1.0,
        "SJF": 1.05
    }

    while True:
        socketio.sleep(1)  # emit every 1 sec

        with app.app_context():
            # Get tasks from DB
            tasks = Task.query.all()

            # Get current battery %
            battery_info = psutil.sensors_battery()
            current_battery = battery_info.percent if battery_info else 100

            battery_history.append(current_battery)
            if len(battery_history) > 10:  # keep last 10 readings
                battery_history.pop(0)

            # Calculate battery used per algorithm
            battery_used_per_algo = {algo: 0 for algo in algo_factors.keys()}
            for task in tasks:
                energy = getattr(task, "energy", 10)  # default energy
                for algo_name, factor in algo_factors.items():
                    battery_used_per_algo[algo_name] += energy * factor

            # Remaining battery for current algorithm
            battery_left = max(current_battery - battery_used_per_algo.get(algorithm, 0), 0)

            # Cap battery_used_per_algo values
            battery_used_per_algo = {k: min(v, 100) for k, v in battery_used_per_algo.items()}

            # Estimate remaining time in minutes
            estimated_time = None
            if len(battery_history) >= 2:
                delta_percent = battery_history[-2] - battery_history[0]
                delta_time = len(battery_history)  # seconds approx
                discharge_rate = delta_percent / delta_time if delta_time != 0 else 0
                if discharge_rate < 0:  # battery decreasing
                    estimated_time = round(current_battery / abs(discharge_rate), 1)

            # Numeric percent for Chart.js
            forecast_percent = max(0, min(100, round(100 - battery_left, 1)))
            forecast_text = f"{estimated_time} mins left" if estimated_time else f"{battery_left}%"

            # Emit to frontend
            socketio.emit("scheduling_update", {
                "battery_left": round(battery_left, 1),
                "battery_used": {k: round(v, 1) for k, v in battery_used_per_algo.items()},
                "currentAlgo": algorithm,
                "forecastPercent": forecast_percent,  # numeric value for chart
                "forecastText": forecast_text        # string for title
            })

# ============================
# Real OS Tasks Integration
# ============================
prev_cpu_times = defaultdict(float)

from datetime import datetime, date

def update_real_tasks(socketio=None, poll_interval=5):
    """
    Keep only today's real live OS tasks in DB.
    Removes old tasks automatically, adds current live tasks,
    and updates progress dynamically based on CPU usage.
    Emits updates only when progress or status changes.
    """
    last_task_state = {}  # store last progress & status for comparison

    while True:
        with app.app_context():
            # Get current live OS processes
            live_pids = set()
            live_processes = {}
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent']):
                try:
                    pid = proc.info['pid']
                    live_pids.add(pid)
                    live_processes[pid] = proc.info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Delete old real tasks not alive or not from today
            old_tasks = Task.query.filter(Task.type == 'real').all()
            for task in old_tasks:
                if task.pid not in live_pids or task.created_at.date() != date.today():
                    db.session.delete(task)
                    last_task_state.pop(task.pid, None)
                    print(f"Deleted old task: {task.name} ({task.pid})")
            db.session.commit()

            # Add new live tasks or update existing tasks
            today_start = datetime.combine(date.today(), datetime.min.time())
            existing_tasks = Task.query.filter(
                Task.type == 'real',
                Task.created_at >= today_start
            ).all()
            existing_pids = {task.pid for task in existing_tasks}

            for pid, info in live_processes.items():
                cpu_percent = info.get('cpu_percent', 0)
                status = info['status'].title()
                progress = int(min(cpu_percent, 100))

                if pid not in existing_pids:
                    # Add new task
                    task = Task(
                        name=info['name'],
                        type='real',
                        status=status,
                        progress=progress,
                        pid=pid,
                        energy=cpu_percent
                    )
                    db.session.add(task)
                    db.session.commit()
                    last_task_state[pid] = (progress, status)
                    socketio.emit("real_task_update", {
                        "task_id": task.id,
                        "pid": pid,
                        "name": task.name,
                        "status": task.status,
                        "progress": task.progress
                    })
                    print(f"Added new live task: {task.name} ({task.pid})")
                else:
                    # Update existing task if progress or status changed
                    task = Task.query.filter_by(pid=pid, type='real').first()
                    if task:
                        prev_progress, prev_status = last_task_state.get(pid, (None, None))
                        if progress != prev_progress or status != prev_status:
                            task.progress = progress
                            task.energy = cpu_percent
                            task.status = status
                            db.session.commit()
                            last_task_state[pid] = (progress, status)
                            socketio.emit("real_task_update", {
                                "task_id": task.id,
                                "pid": pid,
                                "name": task.name,
                                "status": task.status,
                                "progress": task.progress
                            })

        socketio.sleep(poll_interval)

def real_task_scheduler():
    """
    Background loop to update real OS tasks in DB every few seconds.
    """
    while True:
        with app.app_context():
            update_real_tasks(socketio)
        socketio.sleep(1)  # update frequency in seconds

# Start the background thread for real tasks
threading.Thread(target=real_task_scheduler, daemon=True).start()

# ============================
# Helper Functions
# ============================
def add_log(message):
    """Add log entry to DB."""
    try:
        log = Log(message=message)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print("add_log error:", e)

def start_scheduler():
    """Start scheduler thread if not running."""
    global scheduler_thread, CURRENT_SCHEDULER

    if scheduler_thread and scheduler_thread.is_alive():
        print("Scheduler already running.")
        return

    module_name = f"scheduler_{CURRENT_SCHEDULER}"
    try:
        scheduler_module = importlib.import_module(module_name)
    except Exception as e:
        print(f"Failed to import scheduler module '{module_name}': {e}")
        return

    def run_loop():
        try:
            try:
                scheduler_module.scheduler_loop(app, socketio, USER_THRESHOLDS)
            except TypeError:
                scheduler_module.scheduler_loop(app, socketio)
        except Exception as e:
            print("Scheduler thread exception:", e)

    scheduler_thread = Thread(target=run_loop, daemon=True)
    scheduler_thread.start()
    print(f"Started scheduler thread: {module_name}")

def emit_system_stats():
    """Emit CPU/battery stats periodically (throttled)."""
    global current_temperature, battery_history
    last_data = {}
    
    while True:
        try:
            battery = psutil.sensors_battery()
            battery_percent = battery.percent if battery else 100
            cpu_percent = int(psutil.cpu_percent(interval=0.0))
            
            # Smooth battery forecast
            battery_history.append(battery_percent)
            if len(battery_history) > 10:
                battery_history.pop(0)
            smooth_percent = sum(battery_history) / len(battery_history)
            
            data = {
                "battery": round(smooth_percent,1),
                "cpu": cpu_percent,
                "temperature": current_temperature
            }
            
            # Emit only if changed
            if data != last_data:
                socketio.emit("scheduling_update", data)
                last_data = data

        except Exception as e:
            print("emit_system_stats error:", e)
        socketio.sleep(2)  # once per second
# Add the battery collection function here
battery_history = []

def collect_battery_data():
    """Collect battery history and estimate remaining time in minutes."""
    global battery_history
    interval_seconds = 60  # assuming this function runs every 60 seconds

    while True:
        battery = psutil.sensors_battery()
        if battery:
            battery_history.append(battery.percent)
            if len(battery_history) > 10:
                battery_history.pop(0)

            # Smooth battery percent
            smooth_percent = sum(battery_history) / len(battery_history)

            # Calculate discharge rate (percent per second)
            if len(battery_history) >= 2:
                delta_percent = battery_history[-1] - battery_history[0]
                delta_time = (len(battery_history) - 1) * interval_seconds
                discharge_rate = delta_percent / delta_time if delta_time != 0 else 0

                # Estimate remaining time in minutes
                estimated_time = round(smooth_percent / abs(discharge_rate) / 60, 1) if discharge_rate < 0 else None
            else:
                estimated_time = None

            socketio.emit("scheduling_update", {
                "battery": round(smooth_percent, 1),
                "forecast": f"{estimated_time} mins left" if estimated_time else f"{smooth_percent}%",
            })

        socketio.sleep(interval_seconds)


# Start the background thread
threading.Thread(target=collect_battery_data, daemon=True).start()

def calculate_algorithm_battery_impact():
    """
    Calculate dynamic comparative battery impact for all scheduling algorithms
    """
    try:
        # Get current system state
        battery = psutil.sensors_battery()
        current_battery = battery.percent if battery else 100
        cpu_usage = psutil.cpu_percent()
        
        # Get all tasks
        tasks = Task.query.all()
        total_tasks = len(tasks) if tasks else 5
        
        # Base impact factors with more dynamic range
        base_factors = {
            "FCFS": 0.8,
            "Round Robin": 1.2,
            "SJF": 0.7,
            "SRTF": 1.4,
            "Priority Scheduling": 1.6
        }
        
        # Dynamic system multipliers
        system_multiplier = 1.0
        
        # More sensitive battery adjustments
        battery_effect = max(0.5, min(2.0, (100 - current_battery) / 50 + 0.8))
        system_multiplier *= battery_effect
            
        # CPU usage effect - more dynamic
        cpu_effect = max(0.7, min(1.5, cpu_usage / 50))
        system_multiplier *= cpu_effect
            
        # Task load effect
        task_effect = min(2.0, 1.0 + (total_tasks / 8))
        system_multiplier *= task_effect
        
        # Time-based variation for dynamism
        time_variation = 0.9 + (0.2 * math.sin(time.time() / 10))
        system_multiplier *= time_variation

        # Calculate impacts with more variation
        battery_impacts = {}
        base_score = 45  # Slightly higher base for better visualization
        
        for algo, factor in base_factors.items():
            # Base calculation
            impact = base_score * factor * system_multiplier
            
            # Algorithm-specific variations
            algo_variation = random.uniform(0.85, 1.15)
            impact *= algo_variation
            
            # Ensure reasonable bounds with more range
            impact = max(20, min(impact, 85))
            battery_impacts[algo] = round(impact, 1)
            
        return battery_impacts
        
    except Exception as e:
        print(f"calculate_algorithm_battery_impact error: {e}")
        # Return dynamic defaults
        base = random.uniform(25, 40)
        return {
            "FCFS": round(base * 0.8, 1),
            "Round Robin": round(base * 1.2, 1), 
            "SJF": round(base * 0.7, 1),
            "SRTF": round(base * 1.4, 1),
            "Priority Scheduling": round(base * 1.6, 1)
        }

def emit_algorithm_battery_comparison(socketio):
    """
    Continuously emit dynamic battery impacts with frequent updates
    """
    while True:
        try:
            impacts = calculate_algorithm_battery_impact()
            
            socketio.emit("battery_algo_impact", {
                "battery_used": impacts,
                "timestamp": datetime.now().isoformat()
            })
            
            socketio.sleep(1.5)  # More frequent updates for dynamism
            
        except Exception as e:
            print(f"emit_algorithm_battery_comparison error: {e}")
            socketio.sleep(2)
            
# ============================
# Routes
# ============================
@app.route("/")
def index():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    logs = Log.query.order_by(Log.timestamp.desc()).limit(10).all()

    # Convert tasks and logs to simple dicts
    tasks_list = [
        {
            "id": t.id,
            "name": t.name,
            "priority": t.priority,
            "status": t.status,
            "progress": t.progress,
            "energy": t.energy,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for t in tasks
    ]

    logs_list = [
        {
            "id": l.id,
            "task_id": l.task_id,
            "decision": getattr(l, "decision", ""),
            "battery": getattr(l, "battery", 0),
            "cpu": getattr(l, "cpu", 0),
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
            "outcome": getattr(l, "outcome", "")
        }
        for l in logs
    ]

    return render_template(
        "index.html",
        thresholds=USER_THRESHOLDS,
        scheduler_type=CURRENT_SCHEDULER,
        tasks=tasks_list,
        logs=logs_list
    )

@app.route("/tasks")
def tasks_page():
    simulated_tasks=Task.query.filter_by(type='simulated').all()
    real_tasks=Task.query.filter_by(type='real').all()
    all_tasks=simulated_tasks+real_tasks
    return render_template("tasks.html", tasks=all_tasks)

@app.route("/add_task", methods=["POST"])
def add_task():
    name = request.form.get("name")
    priority = request.form.get("priority")  # user input (can be empty)

    if name:
        # Predict with ML model only if user didn't manually select priority
        if (not priority or priority.strip() == "") and priority_model:
            # --- Real-time system stats ---
            cpu = psutil.cpu_percent(interval=0.5)
            battery_info = psutil.sensors_battery()
            battery = battery_info.percent if battery_info else random.uniform(40, 90)

            # --- Dynamic values based on task type ---
            name_lower = name.lower()

            # Base values
            energy = random.uniform(10, 100)
            deadline_hours = random.uniform(1, 24)

            # Adjust dynamically by keyword
            if any(word in name_lower for word in ["render", "simulation", "compile", "encode", "train"]):
                energy = random.uniform(70, 100)
                deadline_hours = random.uniform(1, 6)
            elif any(word in name_lower for word in ["game", "video", "youtube", "movie", "stream"]):
                energy = random.uniform(50, 90)
                deadline_hours = random.uniform(2, 10)
            elif any(word in name_lower for word in ["meeting", "class", "call", "chat", "zoom"]):
                energy = random.uniform(30, 60)
                deadline_hours = random.uniform(1, 5)
            elif any(word in name_lower for word in ["email", "browse", "news", "document", "pdf", "notes"]):
                energy = random.uniform(10, 40)
                deadline_hours = random.uniform(8, 24)
            elif any(word in name_lower for word in ["update", "backup", "install", "upload", "download"]):
                energy = random.uniform(60, 90)
                deadline_hours = random.uniform(1, 8)
            elif any(word in name_lower for word in ["music", "scroll", "social", "media"]):
                energy = random.uniform(20, 60)
                deadline_hours = random.uniform(6, 18)
            else:
                # Default fallback
                energy = random.uniform(30, 70)
                deadline_hours = random.uniform(4, 12)

            # --- Derived features (must match model training) ---
            energy_per_cpu = energy / (cpu if cpu != 0 else 1)
            cpu_battery_ratio = cpu / (battery if battery != 0 else 1)
            deadline_inverse = 1 / (deadline_hours if deadline_hours != 0 else 1)

            features = [[
                energy, deadline_hours, cpu, battery,
                energy_per_cpu, cpu_battery_ratio, deadline_inverse
            ]]

            # --- Predict using model ---
            priority_pred = int(priority_model.predict(features)[0])

            # --- Convert to label ---
            priority_map = {0: "Low", 1: "Medium", 2: "High"}
            priority = priority_map.get(priority_pred, "Medium")

            print(f"🤖 Auto-assigned priority '{priority}' to '{name}' "
                  f"(Energy={energy:.2f}, CPU={cpu:.2f}%, Battery={battery:.2f}%, Deadline={deadline_hours:.2f}h)")

        # --- Save Task ---
        task = Task(name=name, priority=priority, status="Pending")
        db.session.add(task)
        db.session.commit()
        add_log(f"Task added: {name} ({priority})")

    return redirect(url_for("tasks_page"))


@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    task = Task.query.get(task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
        add_log(f"Task deleted: {task.name}")
    return redirect(url_for("tasks_page"))

@app.route('/edit_task/<int:task_id>', methods=['POST'])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    # Update fields from form
    task.name = request.form.get('name')
    task.priority = request.form.get('priority')
    task.status = request.form.get('status')
    task.progress = int(request.form.get('progress', 0))
    task.energy = int(request.form.get('energy', 0))
    
    db.session.commit()
    flash("Task updated successfully!", "success")
    return redirect(url_for('tasks_page'))

@app.route("/update_thresholds", methods=["POST"])
def update_thresholds():
    global USER_THRESHOLDS

    # If reset button is pressed
    if "reset" in request.form:
        # Set your default/original values here
        USER_THRESHOLDS['battery_low'] = 20
        USER_THRESHOLDS['cpu_high'] = 80
        USER_THRESHOLDS['temp_high'] = 70

        add_log("Thresholds reset to defaults: "
                f"battery={USER_THRESHOLDS['battery_low']} "
                f"cpu={USER_THRESHOLDS['cpu_high']} "
                f"temp={USER_THRESHOLDS['temp_high']}")
    else:
        # Update with user-submitted values
        battery = request.form.get("battery_low", type=int)
        cpu = request.form.get("cpu_high", type=int)
        temp = request.form.get("temp_high", type=int)

        if battery is not None: USER_THRESHOLDS['battery_low'] = battery
        if cpu is not None: USER_THRESHOLDS['cpu_high'] = cpu
        if temp is not None: USER_THRESHOLDS['temp_high'] = temp

        add_log("Thresholds updated: "
                f"battery={USER_THRESHOLDS['battery_low']} "
                f"cpu={USER_THRESHOLDS['cpu_high']} "
                f"temp={USER_THRESHOLDS['temp_high']}")

    return redirect(url_for("index"))


@app.route("/set_scheduler/<algo>")
def set_scheduler(algo):
    global CURRENT_SCHEDULER
    algo = algo.lower()
    if algo not in ["priority", "rr"]:
        return redirect(url_for("index"))
    CURRENT_SCHEDULER = algo
    add_log(f"Scheduler set to: {algo}")
    start_scheduler()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    return render_template("index.html", thresholds=USER_THRESHOLDS, scheduler_type=CURRENT_SCHEDULER)

@app.route("/scheduling")
def scheduling():
    simulated_tasks=Task.query.filter_by(type='simulated').all()
    return render_template("scheduling.html",tasks=simulated_tasks)

# Test temperature endpoint
@app.route("/test_temp")
def test_temp():
    """Test all temperature methods"""
    results = {
        "psutil_method": get_temperature_simple(),
        "estimated_method": get_temperature_estimated(),
        "current_global_temperature": current_temperature
    }
    return f"""
    <h3>Temperature Test Results</h3>
    <pre>{results}</pre>
    <p><a href="/">Back to Dashboard</a></p>
    """

# Manual temperature override for testing
@app.route("/set_temp/<float:temp>")
def set_temp(temp):
    """Manually set temperature for testing"""
    global current_temperature
    current_temperature = temp
    return f"Temperature manually set to {temp}°C. <a href='/'>Back to Dashboard</a>"

@app.route('/scheduler-analytics')
def scheduler_analytics():
    # Renders the scheduler analytics page
    return render_template('scheduler-analytics.html')

@app.route('/scheduler-analytics-data')
def scheduler_analytics_data():
    try:
        # Fetch only simulated tasks
        simulated_tasks = Task.query.filter_by(type='simulated').all()
        total_tasks = len(simulated_tasks)

        # Initialize aggregate metrics
        baseline_metrics = {
            "throughput": 0,
            "responseTime": 0,
            "waitTime": 0,
            "cpuUtilization": 0,
            "contextSwitches": 0,
            "turnaroundTime": 0,
            "tasksCompleted": total_tasks
        }

        optimized_metrics = {
            "throughput": 0,
            "responseTime": 0,
            "waitTime": 0,
            "cpuUtilization": 0,
            "contextSwitches": 0,
            "turnaroundTime": 0,
            "tasksCompleted": total_tasks
        }

        # Example: ordinary scheduling -> baseline
        for t in simulated_tasks:
            baseline_metrics["throughput"] += 1  # 1 task completed
            baseline_metrics["cpuUtilization"] += t.energy
            baseline_metrics["responseTime"] += t.response_time
            baseline_metrics["waitTime"] += t.wait_time
            baseline_metrics["turnaroundTime"] += t.turnaround_time
            baseline_metrics["contextSwitches"] += t.context_switches

            # Optimized scheduling effect
            factor = 0.8 if t.priority == "High" else 1.0
            optimized_metrics["throughput"] += 1 * (1.2 if t.priority=="High" else 1.0)
            optimized_metrics["cpuUtilization"] += t.energy * factor
            optimized_metrics["responseTime"] += t.response_time * factor
            optimized_metrics["waitTime"] += t.wait_time * factor
            optimized_metrics["turnaroundTime"] += t.turnaround_time * factor
            optimized_metrics["contextSwitches"] += t.context_switches * factor

        # Average the metrics
        for key in ["responseTime", "waitTime", "turnaroundTime", "cpuUtilization", "contextSwitches"]:
            baseline_metrics[key] = baseline_metrics[key] / total_tasks
            optimized_metrics[key] = optimized_metrics[key] / total_tasks

        return {
            "baseline": baseline_metrics,
            "optimized": optimized_metrics,
            "metadata": {
                "simulationDate": "2025-10-11",
                "totalTasks": total_tasks
            }
        }

    except Exception as e:
        print("scheduler_analytics_data error:", e)
        return {"error": "Failed to fetch analytics data"}, 500


# Register blueprint
app.register_blueprint(scheduling_bp)



# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

    # ----------------- Temperature -----------------
    socketio.emit("temperature_update", {"temperature": current_temperature})

    # ----------------- System stats -----------------
    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else 100
    cpu_percent = int(psutil.cpu_percent(interval=0.0))

    # Estimate battery forecast from history if available
    estimated_time = None
    if len(battery_history) >= 2:
        delta_percent = battery_history[-1] - battery_history[0]
        delta_time = len(battery_history)
        discharge_rate = delta_percent / delta_time if delta_time != 0 else 0
        if discharge_rate < 0:
            estimated_time = round(battery_percent / abs(discharge_rate), 1)

    socketio.emit("scheduling_update", {
        "battery": battery_percent,
        "cpu": cpu_percent,
        "forecast": f"{estimated_time} mins left" if estimated_time else f"{battery_percent}%",
        "temperature": current_temperature
    })

    # ----------------- Current algorithm & battery impact -----------------
    # Get current tasks and progress
    simulated_tasks = Task.query.filter_by(type='simulated').all()
    task_progress = [
        {
            "task": t.name,
            "progress": t.progress,
            "total_energy": t.energy
        }
        for t in simulated_tasks
    ]

    # Send current algorithm and incremental battery info to frontend
    algo_name = CURRENT_SCHEDULER.replace("_", " ").title()  # e.g., "round_robin" -> "Round Robin"
    socketio.emit("battery_algo_impact_init", {
        "algorithm": algo_name,
        "tasks": task_progress,
        "battery": battery_percent
    })



@socketio.on("start_simulation")
def start_simulation(data=None):
    global CURRENT_SCHEDULER

    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else 100
    is_charging = battery.power_plugged if battery else False
    cpu_load = psutil.cpu_percent()

    # Same as scheduler_root.py
    if is_charging:
        algo = "Round Robin"
    elif battery_percent > 50 and cpu_load < 50:
        algo = "Shortest Remaining Time First (SRTF)"
    elif battery_percent <= 20:
        algo = "Priority Scheduling"
    else:
        algo = "Round Robin"

    # Update global tracker
    CURRENT_SCHEDULER = algo.lower().replace(" ", "_")

    # Send algorithm name to frontend
    emit("update_algorithm", {"algorithm": algo,"battery": battery_percent}, broadcast=True)
    
    
    # Start background scheduler
    socketio.start_background_task(run_scheduler_with_intelligence, algo, app, socketio)
    
    socketio.start_background_task(emit_battery_impact_incremental, socketio, algo)

@socketio.on("request_algorithm")
def handle_request_algorithm():
    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else 100

    algo_name = CURRENT_SCHEDULER.replace("_", " ").title()  # e.g., "round_robin" -> "Round Robin"

    # Send current algorithm and battery info
    socketio.emit("update_algorithm", {
        "algorithm": algo_name,
        "battery": battery_percent
    })


# ============================
# Main
# ============================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    eventlet.spawn(start_temperature_monitoring)
    eventlet.spawn(emit_system_stats)

    # Start background scheduler
    socketio.start_background_task(start_scheduler)

    # Start real OS task updater
    socketio.start_background_task(update_real_tasks, socketio)

    print("✅ Server starting...")
    socketio.run(app, debug=True, use_reloader=False)


