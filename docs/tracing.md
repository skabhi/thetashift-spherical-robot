# Trace and timeline

[Handbook](README.md) · [Contents](SUMMARY.md)

Tracing records each instrumented callback's start and elapsed duration.
It can show which logical task step ran after another. It does not show OS
context switches, Wi-Fi stack execution or interrupt identities; gaps are
not proof that the CPU was idle.

## Capture on the ESP32

First leave top/listener with Ctrl+C, then press Ctrl+D at `robot>` to stop
the async console and reach the native `>>>` prompt. Enter:

```python
import robot
robot.capture(5000, capacity=4096)
robot.report()
robot.timeline(40)
robot.save_trace('trace.json')
```

The capture runs tasks for five seconds and returns. Save before starting
another run: each run clears prior statistics and RAM trace data.

Capture duration is 1..60000 ms. Capacity is 1..8192 events and must fit
available RAM. Default capacity 2048 covers approximately 4.6 seconds at
current target rates. A 4096-event buffer uses about 36 KiB plus overhead.
On overflow, the first events remain and later events are counted as omitted.

## Download and open on the computer

Press Ctrl+] to disconnect, then use PowerShell in the repository directory:

```powershell
py -m mpremote connect COM6 fs cp :trace.json trace.json
python build_timeline.py
Start-Process .\captured-timeline.html
```

`build_timeline.py` validates event JSON, creates `trace-data.js` for
`timeline.html`, and builds `captured-timeline.html` with data embedded.
You can also open `timeline.html` and select a downloaded JSON manually.
Generated traces/viewers are ignored by Git and stay on your computer.

Each task has a horizontal row. Adjust Start and Window to inspect time;
hover over a bar for exact microsecond timestamps and duration. Very short
events are drawn at least two pixels wide, so use their measured duration
rather than the displayed width for precise timing.

## Resume

Reconnect using mpremote. At native `>>>`, enter:

```python
import robot
robot.console()
```

EN/RESET also starts the normal boot path. A saved trace file persists on
the ESP32 until overwritten or erased; RAM-only trace data does not.

Next: [Troubleshooting →](troubleshooting.md)
