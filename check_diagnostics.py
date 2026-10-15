"""Host-side checks with MicroPython hardware/time interfaces simulated."""
import asyncio
import gc
import importlib.util
import json
import sys
import tempfile
import time
import types
from pathlib import Path

# Host sandbox blocks asyncio's Windows socketpair setup. These tests use
# timers only, so a selector without wakeup sockets is sufficient.
import selectors
class TimerSelector(selectors.SelectSelector):
    def select(self, timeout=None):
        if timeout:
            time.sleep(timeout)
        return []
class TimerLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(TimerSelector())
    def _make_self_pipe(self):
        self._ssock = self._csock = None
    def _close_self_pipe(self):
        pass
    def _write_to_self(self):
        pass
class TimerPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        return TimerLoop()
asyncio.set_event_loop_policy(TimerPolicy())

root = Path(__file__).parent
wrap = 1 << 30
time.ticks_us = lambda: (time.monotonic_ns() // 1000) % wrap
time.ticks_ms = lambda: (time.monotonic_ns() // 1_000_000) % wrap
time.ticks_add = lambda a, b: (a + b) % wrap
time.ticks_diff = lambda a, b: ((a - b + wrap // 2) % wrap) - wrap // 2
gc.mem_free = lambda: 100000
asyncio.sleep_ms = lambda ms: asyncio.sleep(ms / 1000)
frequency = [160000000]
def freq(value=None):
    if value is not None:
        frequency[0] = value
    return frequency[0]
sys.modules['machine'] = types.SimpleNamespace(freq=freq)
spec = importlib.util.spec_from_file_location('robot', root / 'robot.py')
robot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(robot)

robot.capture(120, capacity=8)
assert robot.bus.topic('task_performance', 0).label == 'motor'
assert robot._resolve_instance('task_performance', 'motor') == 0
assert robot._resolve_instance('task_performance', 'virtual_imu') == 7
subscriptions_before = robot.bus.subscription_count
try:
    robot._resolve_instance('task_performance', 'missing')
except ValueError:
    pass
else:
    raise AssertionError('Missing identity label was accepted')
assert robot.bus.subscription_count == subscriptions_before
assert frequency[0] == 240000000
assert robot._used == 8 and robot._dropped > 0
assert all(s['runs'] > 0 for s in robot._stats)
assert not robot._busy
robot.report()
robot.timeline(2)
with tempfile.TemporaryDirectory(dir=root) as directory:
    path = str(Path(directory) / 'trace.json')
    robot.save_trace(path)
    trace = json.loads(Path(path).read_text())['traceEvents']
    assert len(trace) == 8
    assert all(e['dur'] >= 0 for e in trace)
    assert [e['ts'] for e in trace] == sorted(e['ts'] for e in trace)

# A blocking callback must produce duration overruns and skipped slots.
original = robot.CALLBACKS
robot.CALLBACKS = (('motor', lambda: time.sleep(.025)),)
robot.run(90)
assert robot._stats[0]['overruns'] > 0
assert robot._stats[0]['skipped'] > 0

# A task failure must propagate and execute the motor shutdown hook.
shutdown = []
robot.stop_motors = lambda: shutdown.append(True)
def fail():
    raise RuntimeError('expected test error')
robot.CALLBACKS = (('motor', fail),)
try:
    robot.capture(50)
except RuntimeError as error:
    assert str(error) == 'expected test error'
else:
    raise AssertionError('Task failure was swallowed')
assert shutdown and not robot._busy and robot._stats[0]['errors'] == 1
robot.CALLBACKS = original
robot.capture(30)
assert all(s['runs'] > 0 for s in robot._stats)
print('PASS: frequency, bounded trace, JSON export, overrun/skip detection, failure shutdown, repeated sessions')
