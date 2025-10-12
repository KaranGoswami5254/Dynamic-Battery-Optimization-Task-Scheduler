# scheduling/scheduler.py
import time
from collections import deque

# =========================
# Process Class
# =========================
class Process:
    def __init__(self, pid, burst_time, priority=1, arrival_time=0, io_times=None):
        """
        :param pid: process id
        :param burst_time: total CPU time required
        :param priority: priority value (lower = higher priority)
        :param arrival_time: when the process enters the system
        :param io_times: list of time units when process requests I/O
        """
        self.pid = pid
        self.burst_time = burst_time
        self.priority = priority
        self.arrival_time = arrival_time
        self.io_times = set(io_times or [])  # CPU execution times when I/O is requested
        self.remaining_time = burst_time
        self.cpu_executed = 0
        self.waiting_for_io = False


# =========================
# Simulation Helpers
# =========================
CONTEXT_SWITCH = 1   # overhead in time units
IO_WAIT = 2          # I/O blocking duration

def run_for_one_unit(current, ready_queue, time_elapsed):
    """Run a process for 1 unit, considering I/O blocking"""
    # If process requests I/O
    if current.cpu_executed in current.io_times:
        current.waiting_for_io = True
        return None

    current.remaining_time -= 1
    current.cpu_executed += 1

    return {
        "running": current.pid,
        "queue": [p.pid for p in ready_queue if p.remaining_time > 0 and not p.waiting_for_io]
    }


def context_switch_step(ready_queue):
    """Simulate context switching overhead"""
    return {
        "running": None,
        "queue": [p.pid for p in ready_queue if p.remaining_time > 0 and not p.waiting_for_io]
    }


# =========================
# First Come First Serve
# =========================
def fcfs(processes):
    time_elapsed = 0
    ready_queue = []
    waiting = sorted(processes, key=lambda p: p.arrival_time)

    while waiting or ready_queue:
        # Admit new arrivals
        for p in waiting[:]:
            if p.arrival_time <= time_elapsed:
                ready_queue.append(p)
                waiting.remove(p)

        if not ready_queue:  # idle CPU
            yield {"running": None, "queue": []}
            time.sleep(0.5)
            time_elapsed += 1
            continue

        current = ready_queue.pop(0)

        # Context switch
        for _ in range(CONTEXT_SWITCH):
            yield context_switch_step(ready_queue)
            time.sleep(0.5)
            time_elapsed += 1

        while current.remaining_time > 0:
            step = run_for_one_unit(current, ready_queue, time_elapsed)
            if step:
                yield step
                time.sleep(0.5)
                time_elapsed += 1

            if current.waiting_for_io:
                # simulate I/O wait
                for _ in range(IO_WAIT):
                    yield {"running": None, "queue": [p.pid for p in ready_queue]}
                    time.sleep(0.5)
                    time_elapsed += 1
                current.waiting_for_io = False
                ready_queue.append(current)
                break


# =========================
# Shortest Job First (Non-preemptive)
# =========================
def sjf(processes):
    time_elapsed = 0
    ready_queue = []
    waiting = sorted(processes, key=lambda p: p.arrival_time)

    while waiting or ready_queue:
        # Admit arrivals
        for p in waiting[:]:
            if p.arrival_time <= time_elapsed:
                ready_queue.append(p)
                waiting.remove(p)

        if not ready_queue:
            yield {"running": None, "queue": []}
            time.sleep(0.5)
            time_elapsed += 1
            continue

        # Pick shortest job
        ready_queue.sort(key=lambda p: p.burst_time)
        current = ready_queue.pop(0)

        # Context switch
        for _ in range(CONTEXT_SWITCH):
            yield context_switch_step(ready_queue)
            time.sleep(0.5)
            time_elapsed += 1

        while current.remaining_time > 0:
            step = run_for_one_unit(current, ready_queue, time_elapsed)
            if step:
                yield step
                time.sleep(0.5)
                time_elapsed += 1

            if current.waiting_for_io:
                for _ in range(IO_WAIT):
                    yield {"running": None, "queue": [p.pid for p in ready_queue]}
                    time.sleep(0.5)
                    time_elapsed += 1
                current.waiting_for_io = False
                ready_queue.append(current)
                break


# =========================
# Shortest Remaining Time First (Preemptive SJF)
# =========================
def srtf(processes):
    time_elapsed = 0
    ready_queue = []
    waiting = sorted(processes, key=lambda p: p.arrival_time)

    current = None

    while waiting or ready_queue or (current and current.remaining_time > 0):
        # Admit arrivals
        for p in waiting[:]:
            if p.arrival_time <= time_elapsed:
                ready_queue.append(p)
                waiting.remove(p)

        available = [p for p in ready_queue if p.remaining_time > 0 and not p.waiting_for_io]
        if current and current.remaining_time > 0 and not current.waiting_for_io:
            available.append(current)

        if not available:
            yield {"running": None, "queue": []}
            time.sleep(0.5)
            time_elapsed += 1
            continue

        # Pick process with shortest remaining time
        next_proc = min(available, key=lambda p: p.remaining_time)

        if current != next_proc:
            # context switch if CPU changes process
            for _ in range(CONTEXT_SWITCH):
                yield context_switch_step(ready_queue)
                time.sleep(0.5)
                time_elapsed += 1
            current = next_proc
            if current in ready_queue:
                ready_queue.remove(current)

        step = run_for_one_unit(current, ready_queue, time_elapsed)
        if step:
            yield step
        time.sleep(0.5)
        time_elapsed += 1

        if current.waiting_for_io:
            for _ in range(IO_WAIT):
                yield {"running": None, "queue": [p.pid for p in ready_queue]}
                time.sleep(0.5)
                time_elapsed += 1
            current.waiting_for_io = False
            ready_queue.append(current)
            current = None


# =========================
# Priority Scheduling (Non-preemptive)
# =========================
def priority_scheduling(processes):
    time_elapsed = 0
    ready_queue = []
    waiting = sorted(processes, key=lambda p: p.arrival_time)

    while waiting or ready_queue:
        # Admit arrivals
        for p in waiting[:]:
            if p.arrival_time <= time_elapsed:
                ready_queue.append(p)
                waiting.remove(p)

        if not ready_queue:
            yield {"running": None, "queue": []}
            time.sleep(0.5)
            time_elapsed += 1
            continue

        # Pick highest priority (lower value = higher priority)
        ready_queue.sort(key=lambda p: p.priority)
        current = ready_queue.pop(0)

        # Context switch
        for _ in range(CONTEXT_SWITCH):
            yield context_switch_step(ready_queue)
            time.sleep(0.5)
            time_elapsed += 1

        while current.remaining_time > 0:
            step = run_for_one_unit(current, ready_queue, time_elapsed)
            if step:
                yield step
                time.sleep(0.5)
                time_elapsed += 1

            if current.waiting_for_io:
                for _ in range(IO_WAIT):
                    yield {"running": None, "queue": [p.pid for p in ready_queue]}
                    time.sleep(0.5)
                    time_elapsed += 1
                current.waiting_for_io = False
                ready_queue.append(current)
                break


# =========================
# Round Robin
# =========================
def round_robin(processes, quantum=2):
    time_elapsed = 0
    ready_queue = deque()
    waiting = sorted(processes, key=lambda p: p.arrival_time)

    while waiting or ready_queue:
        # Admit arrivals
        for p in waiting[:]:
            if p.arrival_time <= time_elapsed:
                ready_queue.append(p)
                waiting.remove(p)

        if not ready_queue:
            yield {"running": None, "queue": []}
            time.sleep(0.5)
            time_elapsed += 1
            continue

        current = ready_queue.popleft()

        # Context switch
        for _ in range(CONTEXT_SWITCH):
            yield context_switch_step(ready_queue)
            time.sleep(0.5)
            time_elapsed += 1

        executed = 0
        while executed < quantum and current.remaining_time > 0:
            step = run_for_one_unit(current, ready_queue, time_elapsed)
            if step:
                yield step
                time.sleep(0.5)
                time_elapsed += 1
                executed += 1

            if current.waiting_for_io:
                for _ in range(IO_WAIT):
                    yield {"running": None, "queue": [p.pid for p in ready_queue]}
                    time.sleep(0.5)
                    time_elapsed += 1
                current.waiting_for_io = False
                ready_queue.append(current)
                break

        if current.remaining_time > 0 and not current.waiting_for_io:
            ready_queue.append(current)
