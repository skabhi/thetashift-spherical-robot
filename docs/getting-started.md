# Install and connect

[Handbook](README.md) · [Contents](SUMMARY.md)

## Requirements

The tested board is an original ESP32 / WROOM running MicroPython v1.29.0.
CPU frequency is set to 240 MHz. Other ESP32 variants may require different
firmware and a different maximum frequency in `robot.maximum_performance()`.
The virtual IMU needs no physical sensor or motor hardware.

On your computer install Python and Git. Install the serial tool in PowerShell:

```powershell
py -m pip install --upgrade mpremote
git clone https://github.com/skabhi/thetashift-spherical-robot.git
Set-Location thetashift-spherical-robot
```

If your computer uses `python` instead of `py`, substitute that command.
The uploader itself invokes `python`, so that command must be available.

The examples use COM6. Find your board's port with:

```powershell
py -m mpremote connect list
```

Install the appropriate [MicroPython firmware](https://micropython.org/download/)
before uploading this project. Flashing and erasing firmware removes device
files; routine project updates use the uploader below instead.

## Upload or update

When an existing async console is open, first press Ctrl+C to leave any
listener/monitor, then Ctrl+D at `robot>` to stop tasks and reach `>>>`.
Press Ctrl+] to disconnect. Close other applications using the port.

From the repository directory in PowerShell:

```powershell
.\upload.ps1 -Port COM6
```

This installs official MicroPython aiorepl, copies Python message definitions
and firmware modules, then resets the ESP32. It does not copy host tests,
documentation, traces or Python cache files to the board.

`main.py` starts the robot async console automatically after a normal boot.
If Python reports an import error, check that all modules and `messages/`
were copied; uploading only `robot.py` is insufficient on a fresh board.

## Connect from PowerShell

```powershell
py -m mpremote connect COM6 repl
```

Press Enter if the terminal is blank. The board should show `robot>`.
Opening mpremote does not itself start another copy of the tasks.

## Know which prompt you are using

| Prompt | Where commands execute | Robot tasks |
| --- | --- | --- |
| `PS ...>` | Your Windows computer | Depend on the board's current state |
| `robot>` | Async Python console on ESP32 | Running |
| `>>>` | Native MicroPython REPL on ESP32 | Stopped after leaving the async console |

At native `>>>`, start the robot and async console with:

```python
import robot
robot.console()
```

The word `robot` in the prompt is a label configured in aiorepl. Its useful
behavior comes from running alongside the asyncio event loop. The native
REPL does not keep that event loop running in the background.

## Keyboard controls

| Key | In a listener or top | At idle robot> | At native >>> |
| --- | --- | --- | --- |
| Ctrl+C | Close that tool; tasks continue | Cancel current input | Interrupt executing Python |
| Ctrl+D | First exit the tool with Ctrl+C | Stop tasks; return to native REPL | Soft restart MicroPython |
| Ctrl+] | Exit mpremote; board tasks continue if running | Same | Exit mpremote |

Next: [Console tools →](console-tools.md)
