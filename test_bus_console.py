"""Real-board message-bus/listener tests. Reset into console before running."""
import re
import sys
import time
from pathlib import Path
import serial

root = Path(__file__).parent
log = (root / 'bus-console-serial.log').open('w', encoding='utf-8')
port = serial.Serial(port=None, baudrate=115200, timeout=.1)
port.dtr = port.rts = False
port.port = 'COM6'
port.open()


def receive(marker, timeout=20):
    markers = (marker,) if isinstance(marker, bytes) else marker
    data = b''
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode(errors='replace')
            log.write(text)
            log.flush()
            sys.stdout.write(text)
            sys.stdout.flush()
            data += chunk
            if any(value in data for value in markers):
                return data.decode(errors='replace')
    raise TimeoutError(repr(marker))


def command(text):
    port.write(text.encode() + b'\r')
    output = receive(b'robot> ')
    assert not any(e in output for e in ('Traceback', 'ValueError:', 'RuntimeError:', 'TypeError:', 'NameError:')), output
    return output


try:
    # Do not send Ctrl+C during boot: imports may still be running.
    port.write(b'\x02\r')
    startup = receive((b'robot> ', b'>>> '))
    if 'robot> ' not in startup:
        port.write(b'import robot; robot.console()\r')
        receive(b'robot> ')
    listing = command('await topics()')
    for name in ('imu_sample', 'simulation_state', 'imu_summary', 'task_performance', 'bus_status'):
        assert name in listing
    assert 'logger' not in command("print('TASKS', [x[0] for x in robot.CALLBACKS])").split('TASKS [')[-1]
    stationary = command("await listener('imu_sample', count=2)")
    assert 'simulated: True' in stationary and 'accel_z: 9.806' in stationary
    command("robot.imu_scenario('rotation')")
    rotation = command("await listener('imu_sample', count=2)")
    assert 'gyro_z: 0.5' in rotation
    command("robot.imu_scenario('oscillation')")
    assert 'scenario: oscillation' in command("await listener('simulation_state', count=2)")
    summary = command("await listener('imu_summary', count=2)")
    assert 'accel_magnitude: 9.806' in summary and 'valid: True' in summary
    performance = command("await listener('task_performance', instance=0, count=1)")
    assert 'task_name: motor' in performance
    assert 'publications:' in command("await listener('bus_status', count=1)")
    assert 'logger_enabled: False' in command("await listener('robot_status', count=1)")
    # Finite timeout for advertised topics without any publisher yet.
    waiting = command("await listener('manual_input', count=1, timeout_ms=300)")
    assert 'No new data' in waiting
    baseline = command("print('SUBS', robot.bus.subscription_count)")
    baseline = int(re.search(r'SUBS (\d+)', baseline).group(1))
    # An unknown topic is rejected before allocating a subscription.
    port.write(b"await listener('missing')\r")
    assert 'Unknown topic/instance' in receive(b'robot> ')
    port.write(b"await listener('imu_sample')\r")
    receive(b'gyro_z:')
    port.write(b'\x03')
    assert 'Listener closed' in receive(b'robot> ')
    alive = command("print('ALIVE', robot._busy, robot.bus.subscription_count)")
    assert 'ALIVE True {}'.format(baseline) in alive
    top = command('await robot.top(samples=2, clear=False)')
    assert 'task_performance topics' in top and 'virtual_imu' in top and 'example' in top
    final = command("print('SUBS', robot.bus.subscription_count)")
    assert 'SUBS {}'.format(baseline) in final
    # Select stationary again for the normal startup demo.
    command("robot.imu_scenario('stationary')")
    port.write(b'\x04')
    receive(b'>>> ')
    port.write(b"robot.capture(5000, capacity=4096); robot.report(); robot.save_trace('trace.json'); print('BUS_CAPTURE_PASS')\r")
    capture = receive(b'>>> ', timeout=20)
    assert 'BUS_CAPTURE_PASS' in capture and 'Traceback' not in capture
    print('\nPASS: topics, three IMU modes, template output, performance/bus/status topics, timeout, unknown topic, cancellation cleanup, live top, capture')
finally:
    port.close()
    log.close()
