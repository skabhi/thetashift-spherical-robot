# ThetaShift robot handbook

Build, run and extend the ESP32 MicroPython firmware for the ThetaShift
spherical robot. Start here whether you want to inspect simulated sensors,
understand task performance, or add a new publisher and subscriber.

Read the [documentation website](https://skabhi.github.io/thetashift-spherical-robot/)
for chapter navigation, search, copyable code and light/dark themes. The same
Markdown remains readable on GitHub and compatible with GitBook Git Sync.

## Read in order

1. [Install and connect](getting-started.md): dependencies, upload, COM6 and prompts.
2. [Console tools](console-tools.md): topics, named instances, listener and top.
3. [Tasks and scheduling](tasks.md): task roles, periods and timing limits.
4. [Messages and task extensions](messages.md): schemas, bus API and example task.
5. [Trace and timeline](tracing.md): capture execution and inspect it horizontally.
6. [Troubleshooting](troubleshooting.md): ports, prompts, empty topics and timing.
7. [Tests and measurements](testing.md): host tests and real ESP32 verification.
8. [Publishing the handbook](publishing.md): GitHub navigation and optional GitBook.

The [complete contents](SUMMARY.md) provides the same chapter order.

## What works now

- Independently timed task steps with an asyncio-aware `robot>` prompt.
- A bounded publish/subscribe bus with versioned, hardware-independent messages.
- Virtual IMU scenarios and an example task that computes sensor summaries.
- Live task performance, topic listing, a topic listener and execution tracing.

Physical motor, Wi-Fi, Bluetooth and motion-control logic are placeholders.
No motor outputs are configured. There is no logger task or storage transport.
Scheduling is cooperative, not timer-interrupt-driven or hard real-time.

## First commands

Once the firmware is installed, connect in **PowerShell**:

```powershell
py -m mpremote connect COM6 repl
```

Press Enter and use these at **`robot>`**:

```python
await topics('task_performance')
await listener('task_performance', instance='motor', count=1)
await listener('imu_sample', count=3)
await robot.top()
```

Ctrl+C closes the listener or monitor while robot tasks continue. Ctrl+D
at the idle `robot>` prompt stops tasks and returns to native `>>>`.

Next: [Install and connect →](getting-started.md)
