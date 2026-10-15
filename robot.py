"""ESP32 cooperative task steps and bounded on-demand diagnostics."""
import asyncio
import gc
import machine
from array import array
from time import ticks_us, ticks_ms, ticks_add, ticks_diff

FREQUENCIES_HZ = {
    "motor": 100, "speed_brake": 50, "wifi": 1, "bluetooth": 20,
    "messages": 50, "manual": 50, "velocity": 50, "logger": 1,
}
LOGGER_PRINT = False
# Measured on this ESP32 firmware: positive sleeps wake on coarse ~10 ms
# boundaries, and sleep_ms(10) can take ~20 ms. Keep the event loop runnable
# near a deadline. This deliberately trades CPU/power for timing precision.
WAKE_GUARD_US = 12_000

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
    # TODO: Process a bounded number of queued messages.
    pass

def manual_control():
    pass

def velocity_control():
    pass

def logger():
    # Buffer small entries; avoid blocking flash/serial writes here.
    if LOGGER_PRINT:
        print("Robot uptime: {} ms".format(ticks_diff(ticks_ms(), _start_ms)))

CALLBACKS = (
    ("motor", motor_control), ("speed_brake", speed_and_brake_control),
    ("wifi", wifi_connection), ("bluetooth", bluetooth_control),
    ("messages", messages_server_middleware), ("manual", manual_control),
    ("velocity", velocity_control), ("logger", logger),
)
_stats = []
_trace = None
_used = _dropped = 0
_start_ms = _elapsed_ms = 0
_busy = False


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


async def _periodic(index, name, callback):
    period = round(1_000_000 / FREQUENCIES_HZ[name])
    deadline = _origin_us
    s = _stats[index]
    while True:
        start = ticks_us()
        late = max(0, ticks_diff(start, deadline))
        try:
            callback()
        except Exception:
            s["errors"] += 1
            raise
        end = ticks_us()
        duration = ticks_diff(end, start)
        s["runs"] += 1
        s["total_us"] += duration
        s["max_us"] = max(s["max_us"], duration)
        s["late_us"] = max(s["late_us"], late)
        if duration > period:
            s["overruns"] += 1
        _record(index, start, duration)
        deadline = ticks_add(deadline, period)
        remaining = ticks_diff(deadline, ticks_us())
        if remaining < 0:
            missed = (-remaining + period - 1) // period
            s["skipped"] += missed
            deadline = ticks_add(deadline, missed * period)
            remaining = max(0, ticks_diff(deadline, ticks_us()))
        await _wait_until(deadline)


async def _session(duration_ms):
    global _origin_us, _start_ms
    workers = [asyncio.create_task(_periodic(i, name, callback))
               for i, (name, callback) in enumerate(CALLBACKS)]
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
    workers = [asyncio.create_task(_periodic(i, name, callback))
               for i, (name, callback) in enumerate(CALLBACKS)]
    _origin_us = ticks_us()
    _start_ms = ticks_ms()
    namespace = {"robot": __import__(__name__), "asyncio": asyncio}
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
    previous = [(s["runs"], s["skipped"], s["total_us"]) for s in _stats]
    previous_us = ticks_us()
    frames = 0
    try:
        while samples is None or frames < samples:
            await _wait_until(ticks_add(previous_us, refresh_ms * 1000))
            now = ticks_us()
            window_us = max(1, ticks_diff(now, previous_us))
            current = [(s["runs"], s["skipped"], s["total_us"]) for s in _stats]
            lines = ["\x1b[2J\x1b[H" if clear else "",
                     "ROBOT TOP | {} MHz | window {} ms | heap {} bytes".format(
                         machine.freq() // 1_000_000, window_us // 1000, gc.mem_free()),
                     "task          target live_Hz  runs skip avg_us max_us errors"]
            for (name, _), before, after, s in zip(CALLBACKS, previous, current, _stats):
                runs = after[0] - before[0]
                skipped = after[1] - before[1]
                rate = runs * 1_000_000 / window_us
                avg = (after[2] - before[2]) / max(1, runs)
                lines.append("{:<13} {:>6} {:>7.1f} {:>5} {:>4} {:>6.1f} {:>6} {:>6}".format(
                    name, FREQUENCIES_HZ[name], rate, runs, skipped,
                    avg, s["max_us"], s["errors"]))
                # Formatting eight floating-point rows is also measurable
                # work on the MCU; do not build the screen in one burst.
                await asyncio.sleep_ms(0)
            lines.append("Ctrl+C: close monitor; robot tasks continue. max_us/errors are session totals.")
            # At 115200 baud a whole screen can block ~70 ms. Send bounded
            # chunks and yield between them to keep the control steps running.
            import sys
            text = "\n".join(lines) + "\n"
            for offset in range(0, len(text), 32):
                sys.stdout.write(text[offset:offset + 32])
                await asyncio.sleep_ms(0)
            previous, previous_us = current, now
            frames += 1
    finally:
        print("Monitor closed; robot tasks continue.")


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
