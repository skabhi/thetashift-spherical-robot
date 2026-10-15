"""Real COM6 console test; retains all serial output for inspection."""
import re
import sys
import time
from pathlib import Path
import serial

log = (Path(__file__).parent / 'live-console-serial.log').open('w', encoding='utf-8')
port = serial.Serial(port=None, baudrate=115200, timeout=.1)
port.dtr = False
port.rts = False
port.port = 'COM6'
port.open()

def receive_until(marker, timeout=15, count=1):
    output = b''
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode('utf-8', errors='replace')
            log.write(text)
            log.flush()
            sys.stdout.write(text)
            sys.stdout.flush()
            output += chunk
            if output.count(marker) >= count:
                return output.decode('utf-8', errors='replace')
    raise TimeoutError('Waiting for ' + repr(marker))

def command(text):
    port.write(text.encode() + b'\r')
    return receive_until(b'robot> ')

try:
    # main.py has booted the async console. Ctrl+C redraws its prompt.
    port.write(b'\x02\x03')
    receive_until(b'robot> ')
    finite = command('await robot.top(samples=3, clear=False)')
    assert finite.count('ROBOT TOP |') == 3
    before = command("print('MOTOR_BEFORE', robot._stats[0]['runs'])")
    before = int(re.search(r'MOTOR_BEFORE (\d+)', before).group(1))
    port.write(b'await robot.top(clear=False)\r')
    receive_until(b'Ctrl+C: close monitor', count=2)
    port.write(b'\x03')
    closed = receive_until(b'robot> ')
    assert 'Monitor closed' in closed
    alive = command("print('ALIVE', robot._busy, robot._stats[0]['runs'])")
    match = re.search(r'ALIVE True (\d+)', alive)
    assert match and int(match.group(1)) > before
    command('await robot.top(samples=1, clear=False)')
    port.write(b'\x04')
    receive_until(b'>>> ')
    port.write(b"print('STOPPED', robot._busy); robot.report()\r")
    stopped = receive_until(b'>>> ')
    assert 'STOPPED False' in stopped
    print('\nPASS: live REPL, finite top, Ctrl+C closes top only, robot keeps running, restart top, Ctrl+D exits console')
finally:
    port.close()
    log.close()
