# ThetaShift spherical robot

ESP32 MicroPython firmware for a spherical robot, with independently timed
task steps, a bounded publish/subscribe bus, virtual IMU data, live task
monitoring, a topic listener, and execution timelines.

**[Read the documentation website](https://skabhi.github.io/thetashift-spherical-robot/)**
· [Handbook source](docs/README.md) · [Book contents](docs/SUMMARY.md)
· [Console command reference](docs/console-tools.md)

## Current capabilities

- Nine logical task steps with configurable frequencies and an async `robot>` prompt.
- Versioned messages, independent subscribers, bounded topic storage and loss counters.
- Three virtual IMU scenarios plus a subscribe/process/publish example task.
- Named topic instances, live `top`, a topic `listener`, and trace export.

Physical motor, Wi-Fi, Bluetooth and motion-control logic are placeholders.
There is no scheduled logger while storage is unavailable. The scheduler
uses cooperative asyncio; timer-interrupt scheduling is not implemented.

## Quick start

Tested with an original ESP32 / WROOM, MicroPython v1.29.0 and a 240 MHz CPU.
Install the appropriate MicroPython firmware first. Other ESP32 families may
need a different CPU setting and firmware. The virtual IMU needs no sensor.

In PowerShell:

```powershell
py -m pip install --upgrade mpremote
git clone https://github.com/skabhi/thetashift-spherical-robot.git
Set-Location thetashift-spherical-robot
.\tools\upload.ps1 -Port COM6
py -m mpremote connect COM6 repl
```

Replace COM6 with your board's port. The uploader uses `python`; ensure it
is available. When updating a running board, first close any tool with
Ctrl+C, press Ctrl+D at `robot>` to reach native `>>>`, and press Ctrl+]
to release the port. See [installation](docs/getting-started.md) for details.

At `robot>`:

```python
await topics('task_performance')
await listener('task_performance', instance='motor', count=1)
await listener('imu_sample', count=3)
await robot.top()
```

Ctrl+C closes only the listener/monitor. Ctrl+D at the idle `robot>` prompt
stops tasks and returns to native REPL. Ctrl+] disconnects mpremote.

`topics()` identifies entries directly, for example:

```text
task_performance[0] (motor)
task_performance[7] (virtual_imu)
```

## Handbook

| Chapter | Covers |
| --- | --- |
| [Install and connect](docs/getting-started.md) | Uploading, ports, prompts and keyboard controls |
| [Console tools](docs/console-tools.md) | Topics, named instances, listener, top and every argument |
| [Tasks and scheduling](docs/tasks.md) | Task roles, deadlines, phases and timing limits |
| [Messages and extensions](docs/messages.md) | Schemas, frames, bus API and adding tasks/types |
| [Trace and timeline](docs/tracing.md) | Capture, download, inspect and resume |
| [Troubleshooting](docs/troubleshooting.md) | Busy ports, missing data, old firmware and timing |
| [Tests and measurements](docs/testing.md) | Host tests, hardware checks and measured results |
| [Publish the handbook](docs/publishing.md) | GitHub reading and optional GitBook Git Sync |

The GitHub Pages website provides chapter navigation, full-text search,
copyable code blocks and light/dark themes. Pushes to `main` rebuild and
publish it automatically. The same Markdown is readable on GitHub and
remains compatible with GitBook Git Sync.

## Repository layout

```text
firmware/                  ESP32 sources; uploaded to the board's root
  main.py                  Boot entry point
  robot.py                 Task scheduler and async console tools
  message_bus.py           Bounded publish/subscribe bus
  virtual_imu.py           Simulated sensor publisher
  example_task.py          Subscribe/process/publish example
  messages/                Versioned message definitions
tools/                     Computer-side uploader, trace viewer and helpers
tests/                     Host unit checks and serial integration tests
docs/                      Handbook Markdown sources
mkdocs.yml                 Website theme and navigation
.github/workflows/docs.yml  Build and publish GitHub Pages
artifacts/                 Local trace data and generated viewers (ignored)
```

Firmware files stay flat on the ESP32: the source folder organization does
not change device imports such as `import robot`. Run the examples and tools
from the repository root unless a command says otherwise.

## Development

```powershell
python -m unittest discover -s tests -p test_message_bus.py -v
python tests/check_diagnostics.py
```

Start with [firmware/example_task.py](firmware/example_task.py) for the subscriber/publisher
pattern. Extend definitions under `firmware/messages/` and register tasks in
`firmware/robot.py`.
See the handbook for lifecycle, ownership and uploader requirements.

Normal operation on the tested board achieved motor/IMU rates of 100 Hz
with no skipped slots over a 10-second run. Active console tools reduce
rates; see the [measured workloads](docs/testing.md). This is not a hard
real-time guarantee. Physical shutdown and control logic remain to be built.

Local logs, traces, generated viewers and cache files are ignored by Git.
