# ThetaShift spherical robot

MicroPython starter firmware for a spherical robot, with eight dummy task
steps, independent target frequencies, a live `top` monitor, and an offline
execution timeline. Motor, network, messaging, and control logic are still
placeholders. No motor outputs are configured by this starter.

The current task system uses cooperative `asyncio` scheduling. Timer-driven
scheduling is not implemented yet.

## Get the code

```powershell
git clone https://github.com/skabhi/thetashift-spherical-robot.git
Set-Location thetashift-spherical-robot
```

| Task | Target frequency |
| --- | ---: |
| Motor control | 100 Hz |
| Speed and brake control | 50 Hz |
| Wi-Fi connection | 1 Hz |
| Bluetooth control | 20 Hz |
| Messages server middleware | 50 Hz |
| Manual control | 50 Hz |
| Velocity control | 50 Hz |
| Logger | 1 Hz |

Edit `FREQUENCIES_HZ` and the matching callbacks in `robot.py` to extend it.

## Requirements

- Original ESP32 / WROOM with MicroPython installed; hardware-tested with
  MicroPython v1.29.0. Other ESP32 families need their own firmware and may
  require a different maximum CPU frequency.
- Python on the computer, a USB serial connection, and `mpremote`.
- Official MicroPython `aiorepl`, installed on the ESP32 as shown below.

```powershell
py -m pip install --upgrade mpremote
```

The examples use COM6. Replace it with your board's port. If `py` is not
available, use `python` in its place. Firmware downloads are available at
https://micropython.org/download/ESP32_GENERIC/ .

`main.py` starts `robot.console()` on boot. `robot.py` contains the eight task
steps and the diagnostics. `timeline.html` is an offline trace viewer for
the computer; do not copy the viewer or the host test script to the ESP32.

CPU frequency is set to 240 MHz for the original ESP32 / WROOM each time
`run()` starts. Other ESP32 families may have different supported maxima.

The scheduler uses a shared microsecond release epoch and cooperative
polling within 12 ms of a deadline. Longer waits use ordinary asyncio
sleeps. This avoids the measured coarse wake-up behaviour of this board's
firmware: sleep_ms(10) took about 20 ms. At 100 Hz the polling keeps the
Python event loop runnable much of the time, increasing CPU use and power.
It still yields to other coroutines and does not provide hard real-time
guarantees. Keep callbacks short and nonblocking.

## PowerShell upload

Close any existing mpremote session using Ctrl+]. Then:

```powershell
# Open PowerShell in the folder containing main.py and robot.py.
py -m mpremote connect COM6 mip install aiorepl
py -m mpremote connect COM6 fs cp robot.py :robot.py
py -m mpremote connect COM6 fs cp main.py :main.py
py -m mpremote connect COM6 repl
```

Press EN/RESET to boot the new program. The `robot>` async Python prompt stays
available while tasks run. Ctrl+] exits mpremote without stopping the robot.
In this async prompt Ctrl+D stops tasks and returns to native `>>>`; in the
native prompt Ctrl+D performs the usual soft restart.

## Live top monitor

At the `robot>` prompt:

```python
await robot.top()                          # Redraw every second
```

Ctrl+C closes only the monitor and restores the robot> prompt; the robot
tasks keep running. Run the same command to reopen the monitor. The async
console is MicroPython's official aiorepl library, not the native REPL.
Other options:

```python
await robot.top(refresh_ms=2000)           # Every two seconds
await robot.top(samples=5)                 # Close after five refreshes
await robot.top(clear=False)               # Append screens for logging
robot.report()                            # Snapshot without stopping tasks
```

`live_Hz`, `runs`, `skip`, and `avg_us` refer to the latest measured refresh
window. `max_us` and errors refer to the entire session. The monitor yields
between row calculations and 32-character serial writes so drawing a whole
screen does not block control for a serial screen's entire transmission.
It still has measurement overhead. Avoid blocking Python commands in the
async console, as they pause all cooperative tasks.

To start the async console from a native `>>>` prompt:

```python
import robot
robot.console()
```

## Capture commands from the native REPL

At `robot>` press Ctrl+D first to stop the async console and reach `>>>`.

```python
import robot
robot.report()                    # Statistics of the last run
robot.capture(5000)               # Run tasks for 5 seconds, trace, then stop
robot.report()
robot.timeline(40)                # First 40 steps in execution order
robot.save_trace("trace.json")    # Write trace only after capture
robot.console()                  # Resume tasks and async prompt; clears stats
```

Each capture clears previous statistics and traces. The native REPL and
the event loop do not run concurrently; the async console does support
live commands through aiorepl. Exit that console before timed captures.
The default 2048-event buffer covers about 6 seconds at the configured rates.
On overflow the first events are retained and subsequent events are counted
as omitted; task execution and statistics continue. Maximum capture length
is 60 seconds. Trace storage uses about 18 KiB at default capacity.

Callbacks now use `def`, not `async def`: each invocation is a short step
that must return without blocking. Handle asynchronous network waits in
separate coroutines and communicate through bounded buffers; this trace
will only show the callbacks explicitly instrumented in robot.py.

## Horizontal timeline

After saving the trace, use Ctrl+] to return to PowerShell:

```powershell
py -m mpremote connect COM6 fs cp :trace.json trace.json
Start-Process .\timeline.html
```

Choose the copied trace.json using the viewer's file picker. Set the window
to 1 ms to inspect closely spaced dummy callbacks. Each row is a task and
each bar is one step. Hover to see exact microsecond timestamps and duration.
Two-pixel minimum bar width is a visibility aid, not measured duration.

After downloading a new trace, `python build_timeline.py` validates it and
updates trace-data.js so timeline.html loads it automatically. It also
builds captured-timeline.html with the same trace embedded in one file.

## Statistics and limits

- target / actual: configured Hz / completed runs divided by session time.
  Short sessions exaggerate the apparent rate of slow tasks because every
  task executes immediately at startup; use several seconds for rate checks.
- runs: completed callback invocations.
- skip: releases skipped to avoid catching up in a burst.
- avg_us / max_us: average / maximum elapsed callback duration.
- late_us: maximum delay between scheduled release and actual start.
- over: callbacks whose duration exceeded their own configured period.
- err: callback exceptions; an exception stops the application.

This is not RTOS scheduling or a CPU utilisation profile. The trace records
short synchronous application steps, not OS tasks, interrupt identities,
Wi-Fi stack work, or context switches. Durations may include interruptions
and garbage collection. Gaps include scheduler overhead and waiting; they
cannot be interpreted as CPU idle time. Tracing and statistics add overhead.
Console logging is disabled by default to reduce timing disturbance.

Before implementing physical motor control, implement stop_motors() and
the required command timeout/fault handling. It is currently a placeholder.

Host checks are in check_diagnostics.py and their output is retained in
the local verification logs. They simulate MicroPython interfaces and do
not establish real ESP32 timing or hardware compatibility.

## Verification

From the project directory:

```powershell
python check_diagnostics.py
```

This checks bounded trace storage, JSON export, overrun and skipped-slot
detection, shutdown on callback errors, and repeated sessions. The Windows
host test supplies a timer-only event loop to avoid requiring host sockets.

For the real board, close other serial connections first:

```powershell
# Reset into main.py's async console, then run the interactive serial test.
py -m mpremote connect COM6 reset
python test_live_console.py
```

That test uses COM6 at 115200 baud. It starts and closes the live monitor,
checks that motor counts keep increasing, reopens the monitor, and verifies
that Ctrl+D returns to the native REPL. It finishes with robot tasks stopped.
Use EN/RESET to start the console again.

Measured on the original ESP32 at 240 MHz with dummy callbacks:

| Test | Motor frequency | Motor skipped slots |
| --- | ---: | ---: |
| 30-second normal run | 100.0 Hz | 0 |
| 10-second traced run | 99.96 Hz from event intervals | 0 |
| Live monitor, stop/reopen console test, about 11 seconds | 100.0 Hz | 0 |

These results apply to dummy callbacks, not future real workloads. Timing
still has jitter: the 10-second trace had a longest motor interval of
approximately 16.7 ms. Retest after implementing actual logic.

## Files

- `main.py`: boot entry point.
- `robot.py`: task steps, scheduler, async console, statistics and tracing.
- `timeline.html`: offline viewer; select a downloaded trace JSON.
- `build_timeline.py`: validate a trace and build viewers with it preloaded.
- `check_diagnostics.py`: host simulation checks.
- `test_live_console.py`: real board console and monitor integration check.
- `probe_timing.py`: measure actual asyncio sleep delays on the board.

Local test logs, generated traces and viewers, and old code backups are
ignored by Git. They are not required to install or run the firmware.
