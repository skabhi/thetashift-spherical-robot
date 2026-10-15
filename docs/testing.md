# Tests and measurements

[Handbook](README.md) · [Contents](SUMMARY.md)

## Host checks

From the repository directory:

```powershell
python -m unittest -v test_message_bus
python check_diagnostics.py
python check_docs.py
```

Bus tests cover copied ownership, independent subscribers, latest/queued
delivery, bounds, invalid publications, metadata, schema extension, clock
wrap, IMU consistency and registered labels before first publication.
Diagnostics checks simulate timing interfaces to check trace bounds,
JSON export, overruns, skipped slots, error shutdown and repeated sessions.
They do not establish actual ESP32 timing or hardware compatibility.
The documentation check validates local links and unique chapter navigation.

Run named tests as shown; the serial integration scripts below need hardware
and are not intended for automatic host test discovery.

## Real ESP32 tests

Close other connections to COM6 first. These scripts use COM6 at 115200 baud.
Reset before each test so it starts with the default virtual scenario:

```powershell
py -m mpremote connect COM6 reset
python test_live_console.py
py -m mpremote connect COM6 reset
python test_bus_console.py
py -m mpremote connect COM6 reset
python test_topic_console.py
```

They verify finite and continuous monitors, Ctrl+C cancellation, reopened
tools, robot task progress, subscriber cleanup, three IMU modes, schema
data, unpublished/unknown topics, and capture export. Tests finish at native
`>>>` with tasks stopped, except test_topic_console.py, which verifies
filtered/named topic tools and leaves the async console running. Press
EN/RESET after other tests to start the robot again.

## Measured baseline

Original ESP32 / WROOM, MicroPython v1.29.0, 240 MHz. Physical control tasks
are placeholders; the virtual IMU, bus, example and diagnostics do real work.

| Workload | Motor | Virtual IMU | Skipped slots |
| --- | ---: | ---: | --- |
| 10-second normal run | 100.0 Hz | 100.0 Hz | 0 for all tasks |
| 5-second trace, capacity 4096 | 99.9 Hz | 99.9 Hz | 0 for all tasks |
| Console/listener/top integration, about 12.7 s | 94.4 Hz | 94.0 Hz | Motor 71, IMU 76 |

The trace held 2205 events without overflow. These are measured examples,
not guaranteed rates. Interactive diagnostics perturb timing, and adding
real drivers/controllers changes CPU use. Retest each actual workload.

For a sleep timing probe, stop the async console, disconnect and run:

```powershell
py -m mpremote connect COM6 run probe_timing.py
```

This runs a local measurement script on the board without installing it.
It exits after reporting minimum/mean/maximum wake delays.

Next: [Publishing the handbook →](publishing.md)
