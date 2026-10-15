# ThetaShift spherical robot

MicroPython starter firmware for a spherical robot, with periodic tasks,
a bounded publish/subscribe message bus, a virtual IMU, a live `top` monitor,
a topic `listener`, and an offline execution timeline. Physical motor,
network and control logic remain placeholders. No motor outputs are configured.

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
| Virtual IMU | 100 Hz |
| Example subscriber/publisher | 20 Hz |

There is no scheduled logger task while no storage backend is configured.
The future logger can subscribe without being part of the control data path.

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

`main.py` starts `robot.console()` on boot. `robot.py` contains the task
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

Task deadlines are dispatched by one coroutine, with an independent period
for each logical task. `TASK_PHASE_US` staggers IMU, example and middleware
releases to reduce simultaneous work. This reduces polling overhead compared
with one precision-polling coroutine per task.

## PowerShell upload

Close any existing mpremote session using Ctrl+]. Then:

```powershell
# Open PowerShell in the repository folder. Close other COM6 connections.
.\upload.ps1 -Port COM6
py -m mpremote connect COM6 repl
```

Press EN/RESET to boot the new program. The `robot>` async Python prompt stays
available while tasks run. Ctrl+] exits mpremote without stopping the robot.
In this async prompt Ctrl+D stops tasks and returns to native `>>>`; in the
native prompt Ctrl+D performs the usual soft restart.

When updating an already running async console, press Ctrl+D at `robot>`
to reach native `>>>`, then Ctrl+] to disconnect before uploading. The
upload script installs aiorepl, copies the definitions and firmware, then
restarts the board. It copies only Python sources, not host cache files.

## Topics, virtual IMU and listener

At `robot>`:

```python
await topics()
await listener('imu_sample', count=3)
await listener('imu_summary', count=3)
await listener('task_performance', instance=0, count=3)
await listener('bus_status', count=1)
```

Omit `count` to keep listening; Ctrl+C closes only the listener. Use
`rate_hz=2` to limit display rate (default) and `timeout_ms=5000` to limit
waiting for a topic that has no new data. `robot.listener()` and
`robot.topics()` are equivalent to the short console aliases.

```python
robot.imu_scenario('rotation')       # Constant yaw rate, 0.5 rad/s
robot.imu_scenario('oscillation')    # Sinusoidal roll, consistent IMU data
robot.imu_scenario('stationary')     # Default: level and stationary
await listener('simulation_state', count=3)
```

The example task subscribes to `imu_sample` and publishes `imu_summary`
with acceleration/angular-rate magnitudes and the input sequence number.
See [docs/messages.md](docs/messages.md) for schemas, coordinate frames,
delivery policies, the copy-and-ownership contract, and adding a task/type.

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

`top` subscribes to `task_performance` instances. `live_Hz`, `runs`, `skip`,
and `avg_us` refer to each message's measurement window, published about
once a second. `age_ms` shows publication age; task rows can have slightly
different windows because diagnostics are spread over successive steps.
Initial rows may wait for their first sample. `max_us` and errors refer to
the entire session. The monitor yields
between row calculations and paced 16-character serial writes so drawing a
whole screen does not block control for its entire transmission. It still
has measurement overhead. Parsing/compiling REPL commands, formatting,
serial output and garbage collection can reduce rates while interacting;
the displayed skipped-slot and age counters make this visible. Avoid blocking Python commands in the
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
robot.capture(5000, capacity=4096) # Run for 5 seconds, trace, then stop
robot.report()
robot.timeline(40)                # First 40 steps in execution order
robot.save_trace("trace.json")    # Write trace only after capture
robot.console()                  # Resume tasks and async prompt; clears stats
```

Each capture clears previous statistics and traces. The native REPL and
the event loop do not run concurrently; the async console does support
live commands through aiorepl. Exit that console before timed captures.
The default 2048-event buffer covers about 4.6 seconds at the configured rates.
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
python -m unittest -v test_message_bus
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
# Reset again before the bus/listener integration test.
py -m mpremote connect COM6 reset
python test_bus_console.py
```

That test uses COM6 at 115200 baud. It starts and closes the live monitor,
checks that motor counts keep increasing, reopens the monitor, and verifies
that Ctrl+D returns to the native REPL. It finishes with robot tasks stopped.
Use EN/RESET to start the console again.

The initial scheduler (before adding the message bus and virtual IMU) was
measured on the original ESP32 at 240 MHz with dummy callbacks:

| Test | Motor frequency | Motor skipped slots |
| --- | ---: | ---: |
| 30-second normal run | 100.0 Hz | 0 |
| 10-second traced run | 99.96 Hz from event intervals | 0 |
| Live monitor, stop/reopen console test, about 11 seconds | 100.0 Hz | 0 |

These results apply to dummy callbacks, not future real workloads. Timing
still has jitter: the 10-second trace had a longest motor interval of
approximately 16.7 ms. Retest after implementing actual logic.

After adding the bus, virtual IMU, example task and topic diagnostics, real
ESP32 verification measured:

| Workload | Motor | Virtual IMU | Skipped slots |
| --- | ---: | ---: | --- |
| 10 seconds normal operation | 100.0 Hz | 100.0 Hz | 0 for all tasks |
| 5 seconds tracing, 4096-event buffer | 99.9 Hz | 99.9 Hz | 0 for all tasks |
| Active console/listener/top integration, about 12.7 seconds | 94.4 Hz | 94.0 Hz | Motor 71; IMU 76 |

The integration test deliberately issues many REPL commands and draws
multiple screens. Interactive diagnostics are not timing-neutral. Nine bus
unit tests and the hardware listener tests passed, including cancellation,
subscriber cleanup, three IMU scenarios, an unpublished-topic timeout, and
unknown-topic handling. The 5-second trace held 2205 events without overflow.

## Files

- `main.py`: boot entry point.
- `robot.py`: task steps, scheduler, async console, statistics and tracing.
- `message_bus.py`: bounded topics, independent subscriptions and clock.
- `messages/`: versioned message definitions in SI units.
- `virtual_imu.py`: stationary, rotation and oscillation sensor scenarios.
- `example_task.py`: a reusable subscribe/process/publish task pattern.
- `upload.ps1`: firmware/definition uploader and restart helper.
- `docs/messages.md`: message contracts and extension examples.
- `timeline.html`: offline viewer; select a downloaded trace JSON.
- `build_timeline.py`: validate a trace and build viewers with it preloaded.
- `check_diagnostics.py`: host simulation checks.
- `test_live_console.py`: real board console and monitor integration check.
- `probe_timing.py`: measure actual asyncio sleep delays on the board.
- `test_message_bus.py`: host tests of delivery, ownership and simulated IMU.
- `test_bus_console.py`: real-board listener and message-bus checks.

Local test logs, generated traces and viewers, and old code backups are
ignored by Git. They are not required to install or run the firmware.
