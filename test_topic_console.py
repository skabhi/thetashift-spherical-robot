"""COM6 check for identifiable topics and named instance selection.

Requires the uploaded firmware. Leaves tasks and the async prompt running.
"""
import re
import sys
import time
from pathlib import Path
import serial


def main():
    log_path = Path(__file__).parent / 'topic-console-test.log'
    with log_path.open('w', encoding='utf-8') as log:
        port = serial.Serial(port=None, baudrate=115200, timeout=.1)
        port.dtr = port.rts = False
        port.port = 'COM6'
        port.open()

        def receive(markers=(b'robot> ',), timeout=20):
            data = b''
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                chunk = port.read(port.in_waiting or 1)
                if chunk:
                    text = chunk.decode(errors='replace')
                    log.write(text)
                    log.flush()
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    data += chunk
                    if any(marker in data for marker in markers):
                        return data.decode(errors='replace')
            raise TimeoutError(repr(markers))

        def command(text, error=None):
            port.write(text.encode() + b'\r')
            output = receive()
            assert 'Traceback' not in output
            if error:
                assert error in output
            else:
                assert not any(kind in output for kind in ('ValueError:', 'RuntimeError:', 'TypeError:'))
            return output

        def subscriber_count():
            output = command("print('SUBS', robot.bus.subscription_count)")
            return int(re.search(r'SUBS (\d+)', output).group(1))

        try:
            port.write(b'\x02\r')
            startup = receive((b'robot> ', b'>>> '))
            if 'robot> ' not in startup:
                port.write(b'import robot; robot.console()\r')
                receive()
            before = subscriber_count()
            listing = command("await topics('task_performance')")
            names = ('motor', 'speed_brake', 'wifi', 'bluetooth', 'messages',
                     'manual', 'velocity', 'virtual_imu', 'example')
            for index, name in enumerate(names):
                assert 'task_performance[{}] ({})'.format(index, name) in listing
            assert 'imu_sample[0]' not in listing
            named = command("await listener('task_performance', instance='motor', count=1)")
            assert 'task_performance[0] (motor)' in named and 'task_name: motor' in named
            numeric = command("await listener('task_performance', instance=7, count=1)")
            assert 'task_performance[7] (virtual_imu)' in numeric
            command("await listener('task_performance', instance='missing', count=1)",
                    error='Unknown or ambiguous instance label')
            command("await topics('missing')", error='Unknown topic')
            assert subscriber_count() == before
            assert 'imu_sample[0]' in command('await topics()')
            assert 'RUNNING True' in command("print('RUNNING', robot._busy)")
            print('\nPASS: all nine identities, filtered listing, named/numeric listeners, invalid selectors, no subscription leaks, tasks remain running')
        finally:
            port.close()


if __name__ == '__main__':
    main()
