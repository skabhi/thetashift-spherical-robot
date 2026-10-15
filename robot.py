"""ESP32 cooperative task steps and bounded on-demand diagnostics."""
import asyncio
import gc
import machine
from array import array
from time import ticks_us, ticks_ms, ticks_add, ticks_diff
from message_bus import Bus
from messages import (TASK_PERFORMANCE, BUS_STATUS, IMU_SAMPLE, SIMULATION_STATE,
                      ROBOT_STATUS, MANUAL_INPUT, VELOCITY_SETPOINT, IMU_SUMMARY)
from virtual_imu import VirtualIMU
from example_task import ExampleTask

FREQUENCIES_HZ = {
    "motor": 100, "speed_brake": 50, "wifi": 1, "bluetooth": 20,
    "messages": 50, "manual": 50, "velocity": 50,
    "virtual_imu": 100, "example": 20,
}
# Measured on this ESP32 firmware: positive sleeps wake on coarse ~10 ms
# boundaries, and sleep_ms(10) can take ~20 ms. Keep the event loop runnable
# near a deadline. This deliberately trades CPU/power for timing precision.
WAKE_GUARD_US = 12_000
# Spread the two high-rate releases and diagnostic work across the cycle.
TASK_PHASE_US = {"virtual_imu": 5000, "example": 8000, "messages": 2000}

# Callbacks are short SYNCHRONOUS steps: no sleep or blocking I/O.
def motor_control():
    # TODO: Apply outputs using hardware PWM.
    pass

def speed_and_brake_control():
    pass

def wifi_connection():
    # TODO: Check state/start a retry, then return without waiting.
    pass

def bluetooth_control():
    pass

def messages_server_middleware():
    # Publish/subscribe itself is synchronous; this task publishes diagnostics
    # one topic per invocation so a complete screen's work is not one burst.
    global _diag_index, _next_diag_us
    now = bus.clock.now_us()
    if _diag_index < 0:
        if now < _next_diag_us:
            return
        _diag_index = 0
        _next_diag_us = now + 1_000_000
    index = _diag_index
    if index < len(CALLBACKS):
        name = CALLBACKS[index][0]
        s = _stats[index]
        before = _diag_previous[index]
        window = max(1, now - before[3])
        runs = s["runs"] - before[0]
        payload = _performance_payload
        payload.update(task_id=index, task_name=name, target_hz=FREQUENCIES_HZ[name],
                       window_us=window, runs=runs, measured_hz=runs * 1_000_000 / window,
                       skipped=s["skipped"] - before[1],
                       avg_us=(s["total_us"] - before[2]) / max(1, runs),
                       max_us=s["max_us"], late_us=s["late_us"], errors=s["errors"])
        bus.topic("task_performance", index).publish(payload, source_id=3)
        _diag_previous[index] = (s["runs"], s["skipped"], s["total_us"], now)
    elif index == len(CALLBACKS):
        _bus_payload.update(topics=len(bus.topics), subscriptions=bus.subscription_count,
                            publications=bus.publications, retained_overwrites=bus.retained_overwrites,
                            subscriber_missed=bus.subscriber_missed, queue_evictions=bus.queue_evictions,
                            free_heap_bytes=gc.mem_free())
        bus.topic("bus_status").publish(_bus_payload, source_id=3)
    else:
        bus.topic("robot_status").publish(_robot_payload, source_id=3)
    _diag_index += 1
    if _diag_index >= len(CALLBACKS) + 2:
        _diag_index = -1

def manual_control():
    pass

def velocity_control():
    pass

def virtual_imu_task():
    _virtual_imu.step()


def example_task():
    _example.step()

CALLBACKS = (
    ("motor", motor_control), ("speed_brake", speed_and_brake_control),
    ("wifi", wifi_connection), ("bluetooth", bluetooth_control),
    ("messages", messages_server_middleware), ("manual", manual_control),
    ("velocity", velocity_control), ("virtual_imu", virtual_imu_task),
    ("example", example_task),
)
_stats = []
_trace = None
_used = _dropped = 0
_start_ms = _elapsed_ms = 0
_busy = False
bus = None
_session_id = 0


def _setup_messages():
    global bus, _session_id, _virtual_imu, _example
    global _diag_index, _next_diag_us, _diag_previous
    global _performance_payload, _bus_payload, _robot_payload
    _session_id += 1
    bus = Bus(session_id=_session_id)
    for name, definition in (("imu_sample", IMU_SAMPLE), ("simulation_state", SIMULATION_STATE),
                             ("imu_summary", IMU_SUMMARY), ("bus_status", BUS_STATUS),
                             ("robot_status", ROBOT_STATUS), ("manual_input", MANUAL_INPUT),
                             ("velocity_setpoint", VELOCITY_SETPOINT)):
        bus.advertise(name, definition)
    for index in range(len(CALLBACKS)):
        bus.advertise("task_performance", TASK_PERFORMANCE, instance=index,
                      label=CALLBACKS[index][0])
    _performance_payload = TASK_PERFORMANCE.new()
    _bus_payload, _robot_payload = BUS_STATUS.new(), ROBOT_STATUS.new()
    _diag_previous = [(0, 0, 0, bus.clock.now_us()) for _ in CALLBACKS]
    _diag_index = -1
    _next_diag_us = bus.clock.now_us() + 1_000_000
    _virtual_imu = VirtualIMU(bus)
    _example = ExampleTask(bus)
    bus.topic("robot_status").publish(_robot_payload, source_id=3)


def imu_scenario(name):
    """Select stationary, rotation or oscillation on the virtual IMU."""
    if not _busy:
        raise RuntimeError("Start the robot first")
    _virtual_imu.set_scenario(name)


def maximum_performance():
    # Original ESP32 / WROOM: documented maximum is 240 MHz.
    machine.freq(240_000_000)
    return machine.freq()


def stop_motors():
    # TODO: Disable physical outputs here before implementing motor logic.
    pass


def _record(index, start, duration):
    global _used, _dropped
    if _trace is None:
        return
    if _used == len(_trace[0]):
        _dropped += 1
        return
    _trace[0][_used] = index
    _trace[1][_used] = ticks_diff(start, _origin_us)
    _trace[2][_used] = duration
    _used += 1


async def _wait_until(deadline):
    # Always yield, including when already late, so peers can make progress.
    await asyncio.sleep_ms(0)
    while True:
        remaining = ticks_diff(deadline, ticks_us())
        if remaining <= 0:
            return
        if remaining > WAKE_GUARD_US:
            await asyncio.sleep_ms(max(1, (remaining - WAKE_GUARD_US) // 1000))
        else:
            await asyncio.sleep_ms(0)


async def _scheduler():
    # One dispatcher avoids nine separate precision-polling coroutines.
    # These remain independently timed logical tasks with separate deadlines.
    jobs = [(name, callback, round(1_000_000 / FREQUENCIES_HZ[name]))
            for name, callback in CALLBACKS]
    deadlines = [ticks_add(_origin_us, TASK_PHASE_US.get(name, 0) % period)
                 for name, _, period in jobs]
    while True:
        for index, (name, callback, period) in enumerate(jobs):
            start = ticks_us()
            late = ticks_diff(start, deadlines[index])
            if late < 0:
                continue
            s = _stats[index]
            try:
                callback()
            except Exception:
                s["errors"] += 1
                raise
            duration = ticks_diff(ticks_us(), start)
            s["runs"] += 1
            s["total_us"] += duration
            s["max_us"] = max(s["max_us"], duration)
            s["late_us"] = max(s["late_us"], late)
            if duration > period:
                s["overruns"] += 1
            _record(index, start, duration)
            deadline = ticks_add(deadlines[index], period)
            remaining = ticks_diff(deadline, ticks_us())
            if remaining < 0:
                missed = (-remaining + period - 1) // period
                s["skipped"] += missed
                deadline = ticks_add(deadline, missed * period)
            deadlines[index] = deadline
            await asyncio.sleep_ms(0)
        now = ticks_us()
        remaining = min(ticks_diff(deadline, now) for deadline in deadlines)
        await _wait_until(ticks_add(now, max(0, remaining)))


async def _session(duration_ms):
    global _origin_us, _start_ms
    workers = [asyncio.create_task(_scheduler())]
    timer = None
    timed_out = [False]
    async def timeout():
        await _wait_until(ticks_add(_origin_us, duration_ms * 1000))
        timed_out[0] = True
        for worker in workers:
            worker.cancel()
    try:
        # Use one epoch for all releases and the capture cutoff. Exclude
        # asyncio startup/worker creation from measured session duration.
        _origin_us = ticks_us()
        _start_ms = ticks_ms()
        if duration_ms is not None:
            timer = asyncio.create_task(timeout())
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            if not timed_out[0]:
                raise
    finally:
        if timer is not None:
            timer.cancel()
        for worker in workers:
            worker.cancel()


async def _console_session():
    """Keep an asyncio-aware Python prompt alive beside the robot tasks."""
    import aiorepl
    global _origin_us, _start_ms
    workers = [asyncio.create_task(_scheduler())]
    _origin_us = ticks_us()
    _start_ms = ticks_ms()
    namespace = {"robot": __import__(__name__), "asyncio": asyncio,
                 "listener": listener, "topics": topics}
    shell = asyncio.create_task(aiorepl.task(namespace, prompt="robot> "))
    failure = [None]
    async def supervise():
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass
        except Exception as error:
            failure[0] = error
            shell.cancel()
    supervisor = asyncio.create_task(supervise())
    print("Robot tasks active. await robot.top() monitors; Ctrl+C exits top.")
    print("Ctrl+D exits the async console and stops the robot tasks.")
    try:
        try:
            await shell
        except asyncio.CancelledError:
            if failure[0] is None:
                raise
        if failure[0] is not None:
            raise failure[0]
    finally:
        supervisor.cancel()
        for worker in workers:
            worker.cancel()


def console():
    """Start robot tasks and the async REPL. Call from native >>> prompt."""
    run(console=True)


def run(duration_ms=None, trace=False, capacity=2048, console=False):
    """Run until Ctrl+C or duration. A new run clears diagnostics."""
    global _stats, _trace, _used, _dropped, _origin_us
    global _start_ms, _elapsed_ms, _busy
    if _busy:
        raise RuntimeError("Already running")
    if console and (duration_ms is not None or trace):
        raise ValueError("Console mode requires an untimed, untraced run")
    if duration_ms is not None and not 1 <= duration_ms <= 60_000:
        raise ValueError("duration_ms must be 1..60000")
    if trace and duration_ms is None:
        raise ValueError("Use a timed capture for tracing")
    if trace and not 1 <= capacity <= 8192:
        raise ValueError("capacity must be 1..8192")
    for name, _ in CALLBACKS:
        if not 1 <= FREQUENCIES_HZ[name] <= 1000:
            raise ValueError("Frequency must be 1..1000 Hz")
    cpu = maximum_performance()
    _stats = [dict(runs=0, skipped=0, total_us=0, max_us=0,
                   late_us=0, overruns=0, errors=0) for _ in CALLBACKS]
    _setup_messages()
    # Bounded storage: approximately 18 KiB for 2048 events.
    _trace = (bytearray(capacity),
              array("i", (0 for _ in range(capacity))),
              array("i", (0 for _ in range(capacity)))) if trace else None
    _used = _dropped = 0
    print("CPU: {} MHz; trace: {}".format(cpu // 1_000_000, trace))
    gc.collect()
    _origin_us = ticks_us()
    _start_ms = ticks_ms()
    _busy = True
    try:
        asyncio.run(_console_session() if console else _session(duration_ms))
    except KeyboardInterrupt:
        pass
    finally:
        _elapsed_ms = ticks_diff(ticks_ms(), _start_ms)
        _busy = False
        stop_motors()
        _example.close()
        asyncio.new_event_loop()
        print("Stopped after {} ms".format(_elapsed_ms))


def capture(duration_ms=1000, capacity=2048):
    """Run from REPL, then return. Does not auto-resume."""
    run(duration_ms, trace=True, capacity=capacity)


def report():
    if not _stats:
        print("No session yet")
        return
    elapsed = ticks_diff(ticks_ms(), _start_ms) if _busy else _elapsed_ms
    print("CPU {} MHz; session {} ms; free heap {} bytes".format(
        machine.freq() // 1_000_000, elapsed, gc.mem_free()))
    print("task          target actual   runs skip avg_us max_us late_us over err")
    for (name, _), s in zip(CALLBACKS, _stats):
        actual = s["runs"] * 1000 / max(1, elapsed)
        avg = s["total_us"] / max(1, s["runs"])
        print("{:<13} {:>6} {:>6.1f} {:>6} {:>4} {:>6.1f} {:>6} {:>7} {:>4} {:>3}".format(
            name, FREQUENCIES_HZ[name], actual, s["runs"], s["skipped"],
            avg, s["max_us"], s["late_us"], s["overruns"], s["errors"]))
    print("Trace events: {}; omitted after buffer full: {}".format(_used, _dropped))


async def top(refresh_ms=1000, samples=None, clear=True):
    """Live interval rates. In aiorepl use await robot.top(); Ctrl+C exits."""
    if not _busy:
        raise RuntimeError("Start robot.console() first")
    if refresh_ms < 250:
        raise ValueError("refresh_ms must be >=250 to limit console traffic")
    if samples is not None and samples < 1:
        raise ValueError("samples must be >=1")
    subscriptions = [bus.subscribe("task_performance", index) for index in range(len(CALLBACKS))]
    latest = [{} for _ in CALLBACKS]
    frames = 0
    try:
        while samples is None or frames < samples:
            await _wait_until(ticks_add(ticks_us(), refresh_ms * 1000))
            lines = ["\x1b[2J\x1b[H" if clear else "",
                     "ROBOT TOP | {} MHz | task_performance topics | heap {} bytes".format(
                         machine.freq() // 1_000_000, gc.mem_free()),
                     "task          target live_Hz  runs skip avg_us max_us errors age_ms"]
            for (name, _), sub, sample in zip(CALLBACKS, subscriptions, latest):
                sub.read_into(sample)
                if sample:
                    age = max(0, bus.clock.now_us() - sample["timestamp_us"]) // 1000
                    lines.append("{:<13} {:>6} {:>7.1f} {:>5} {:>4} {:>6.1f} {:>6} {:>6} {:>6}".format(
                        name, sample["target_hz"], sample["measured_hz"], sample["runs"],
                        sample["skipped"], sample["avg_us"], sample["max_us"], sample["errors"], age))
                else:
                    lines.append("{}: waiting for first performance sample".format(name))
                await asyncio.sleep_ms(0)
            lines.append("Ctrl+C: close monitor; robot tasks continue. max_us/errors are session totals.")
            await _console_write("\n".join(lines) + "\n")
            frames += 1
    finally:
        for sub in subscriptions:
            sub.close()
        print("Monitor closed; robot tasks continue.")


async def _console_write(text):
    import sys
    # Pace below UART line rate as well as yielding. Otherwise successive
    # chunks fill the ESP32 TX buffer and a later write can block for a
    # coarse RTOS tick even though each individual chunk is small.
    for offset in range(0, len(text), 16):
        sys.stdout.write(text[offset:offset + 16])
        await _wait_until(ticks_add(ticks_us(), 5000))


async def topics(name=None):
    """List topic identities; optionally filter by an exact topic name."""
    if bus is None:
        raise RuntimeError("Start the robot first")
    keys = sorted(key for key in bus.topics if name is None or key[0] == name)
    if not keys:
        raise ValueError("Unknown topic; use await topics()")
    await _console_write("topic[instance] (identity)                  schema v  depth  sequence  subs\n")
    for key in keys:
        topic = bus.topics[key]
        identity = "{}[{}]".format(topic.name, topic.instance)
        if topic.label:
            identity += " ({})".format(topic.label)
        await _console_write("{:<42} {} v{}  {}  {}  {}\n".format(
            identity, topic.schema.name, topic.schema.version,
            topic.depth, topic.sequence, len(topic.subscribers)))


def _resolve_instance(name, instance):
    if type(instance) is str:
        matches = [topic.instance for topic in bus.topics.values()
                   if topic.name == name and topic.label == instance]
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous instance label; use await topics()")
        return matches[0]
    if type(instance) is not int or instance < 0:
        raise ValueError("instance must be a nonnegative number or an identity label")
    return instance


async def listener(name, instance=0, count=None, rate_hz=2, timeout_ms=5000):
    """Print snapshots without stopping robot tasks; Ctrl+C closes listener.

    A slow listener intentionally downsamples latest-sample topics. A queued
    topic is drained one message at a time at the selected display rate.
    """
    if bus is None:
        raise RuntimeError("Start the robot first")
    if count is not None and (type(count) is not int or count < 1):
        raise ValueError("count must be a positive integer or None")
    if not 0.1 <= rate_hz <= 10 or not 1 <= timeout_ms <= 60_000:
        raise ValueError("rate_hz must be 0.1..10 and timeout_ms 1..60000")
    instance = _resolve_instance(name, instance)
    if (name, instance) not in bus.topics:
        raise ValueError("Unknown topic/instance; use await topics()")
    sub = bus.subscribe(name, instance)
    sample = {}
    printed = 0
    last_data = ticks_ms()
    try:
        while count is None or printed < count:
            if sub.read_into(sample):
                last_data = ticks_ms()
                label = " ({})".format(sub.topic.label) if sub.topic.label else ""
                await _console_write("\n{}[{}]{} sequence={} missed={}\n".format(
                    name, instance, label, sample["sequence"], sub.missed))
                for key, value in sample.items():
                    await _console_write("  {}: {}\n".format(key, value))
                printed += 1
                if count is None or printed < count:
                    await _wait_until(ticks_add(ticks_us(), round(1_000_000 / rate_hz)))
            elif ticks_diff(ticks_ms(), last_data) >= timeout_ms:
                await _console_write("No new data on {}[{}] within {} ms\n".format(name, instance, timeout_ms))
                break
            else:
                await asyncio.sleep_ms(0)
    finally:
        sub.close()
        print("Listener closed; robot task state unchanged.")


def timeline(limit=40):
    if _trace is None:
        print("Run capture() first")
        return
    print("start_us  end_us    task          duration_us")
    for i in range(min(limit, _used)):
        name = CALLBACKS[_trace[0][i]][0]
        start, duration = _trace[1][i], _trace[2][i]
        print("{:>8} {:>8} {:<13} {}".format(start, start + duration, name, duration))


def save_trace(path="trace.json"):
    """Export Chrome Trace Event JSON, one event at a time."""
    import json
    if _trace is None:
        raise RuntimeError("Run capture() first")
    with open(path, "w") as output:
        output.write('{"traceEvents":[')
        for i in range(_used):
            if i:
                output.write(",")
            index = _trace[0][i]
            output.write(json.dumps(dict(
                name=CALLBACKS[index][0], ph="X", pid=1, tid=index,
                ts=_trace[1][i], dur=_trace[2][i])))
        output.write('],"displayTimeUnit":"ms"}')
    print("Saved {} events to {}".format(_used, path))
