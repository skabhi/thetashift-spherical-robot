# Messages and task extension guide

[Handbook](README.md) · [Contents](SUMMARY.md)

This is a small uORB-inspired bus implemented for one MicroPython asyncio
event loop, not PX4 uORB wire compatibility. Topics are local to the MCU.
No threads, interrupt callbacks, device files or external broker are needed.

## Available topics

| Topic | Publisher | Rate | Contents |
| --- | --- | ---: | --- |
| `imu_sample` | Virtual IMU | 100 Hz target | Specific force, angular rate, sample time, frame, validity, simulated flag |
| `simulation_state` | Virtual IMU | Approximately 20 Hz | Ideal orientation quaternion and angular rate for validation |
| `imu_summary` | Example task | 20 Hz target | Vector magnitudes and input sequence |
| `task_performance` | Middleware diagnostics | Approximately 1 Hz per instance | Per-task interval counts/rates and session maxima/errors |
| `bus_status` | Middleware diagnostics | Approximately 1 Hz | Bus counters, subscriptions and free heap |
| `robot_status` | Middleware diagnostics | On start, then approximately 1 Hz | Simulation mode, disabled actuators, storage/logger unavailable |
| `manual_input` | Reserved for a future input adapter | No publisher yet | Normalized motion/enable/brake requests and expiry |
| `velocity_setpoint` | Reserved for a future controller | No publisher yet | Planar velocity and yaw-rate target, frame, validity and expiry |

Each task has a separate `task_performance` instance. Currently: motor=0,
speed_brake=1, wifi=2, bluetooth=3, messages=4, manual=5, velocity=6,
virtual_imu=7, example=8. The mapping follows `robot.CALLBACKS`; always check
`task_name` rather than relying on a permanent numeric assignment.
`await topics('task_performance')` shows these names beside the instance
numbers. You can select them with `instance='motor'` or
`instance='virtual_imu'` in listener commands. Labels are registration metadata,
so identification works even before the first sample is published.

There are no assumptions about motor count, servo layout, encoder type or
physical sensor model. Those definitions can be added once hardware is chosen.

## Definition contract

Definitions are fixed scalar layouts in `firmware/messages/`, each with a schema
version. Field kinds are `u` (nonnegative integer), `f` (int/float number),
`b` (boolean), and `s` (string limited to 48 characters). Units and semantics
are documented beside the definitions. Types are checked on every publish;
missing/extra fields are rejected before the publication sequence changes.
Consumers must also check validity, command expiry and application-specific
ranges before applying actual controls. Type checking is not a safety policy.

Every received sample includes this header, supplied by the bus:

| Field | Meaning |
| --- | --- |
| `timestamp_us` | Publication time from a shared extended monotonic clock |
| `sequence` | Per-topic-instance publication sequence, starting at 1 |
| `source_id` | Publisher identity: virtual IMU=1, example=2, diagnostics=3 |
| `instance_id` | Topic instance, e.g. IMU or task index |
| `schema_version` | Definition version |
| `session_id` | Run counter within this interpreter; resets after MCU reboot |

Each `robot.run()`/`robot.console()` creates a new bus and clock. Timestamps
are microseconds since that bus was constructed, not UTC, and not guaranteed
to start at MCU power-on. The extended clock handles ticks wrap provided
it is sampled at least once per half ticks period. The running IMU and
middleware sample it continually. A future logger should write a recording
header with a boot/session identifier rather than treat session_id as a
globally unique identifier. Sensor messages additionally carry sample time,
separate from publication time.

## Delivery and memory ownership

- `advertise(name, definition, instance=0, depth=1, label='')` creates a bounded
  topic with optional human-readable identity metadata (up to 48 characters).
- `publish(payload, source_id=...)` validates and copies scalar values into
  an immutable tuple. The publisher may reuse its original payload dict.
- `subscribe(name, instance=0, replay=True)` gives each consumer its own
  cursor. The default subscription replays the latest existing sample once.
- `updated()` checks for unread data. `read_into(owned_dict)` copies one
  available sample and advances only that subscription's cursor.
- `read()` is an allocating convenience method; hot tasks should use
  `read_into()`. The output dict includes the common header.
- `close()` releases a subscription. Console tools close theirs on normal
  return, errors, timeout and Ctrl+C.

Depth 1 means latest-sample delivery. Faster publications replace older
samples. Subscribers that intentionally run slowly will count missed
sequences: that is expected downsampling, not proof of a bus failure.
For future event topics, specify depth 2..32 for a bounded FIFO. Subscribers
read retained events in order and count lost sequences if they fall behind.
This queue cannot guarantee delivery; critical events also need appropriate
acknowledgement, timeout and/or latched state in their eventual design.

The default bus allows 32 topic instances and 64 subscriptions; attempts to
exceed them raise an error. Retained storage stays bounded. `bus_status` has
distinct counters for normal retained overwrites, subscriber sequence gaps
observed on read, and unread per-subscriber evictions from queued topics.
It is a snapshot and excludes its own publication from its publication count.

Publishing does not invoke subscriber code or wait for the middleware task.
The middleware task only publishes diagnostic snapshots, spreading work
across invocations. All bus access must happen in the same cooperative
event loop. It is not safe from hardware IRQs or concurrent threads.

## Virtual IMU conventions

The virtual sensor uses `internal_body`: x forward, y left, z up, with a
right-handed convention. Its quaternion maps that frame into `world_z_up`.
The virtual accelerometer measures specific force in m/s^2; at rest and
level accel_z is +9.80665. Angular rate is rad/s. Validity bit 0 denotes
acceleration and bit 1 denotes gyro data. Simulated data is explicitly tagged.

- `stationary`: identity orientation, zero angular rate.
- `rotation`: yaw rate +0.5 rad/s; gravity reading stays level.
- `oscillation`: roll amplitude 0.25 rad at 0.5 Hz; gyro is its analytical
  derivative and the gravity reading rotates consistently into sensor frame.

This models an ideal sensor at a fixed pivot with no translation, noise,
bias or centrifugal acceleration. It is not a rolling-sphere dynamics model.
A physical IMU mounted on the shell will need a different frame and motion
model from one on an internal chassis.

## Topic listener

At the async `robot>` prompt:

```python
await topics()
await topics('task_performance')
await listener('imu_sample')
await listener('imu_sample', count=3, rate_hz=2)
await listener('task_performance', instance='motor', count=1)
```

Ctrl+C stops only the listener and returns to the prompt. It does not stop
tasks or consume another subscriber's messages. `rate_hz` limits output,
not publisher frequency. A missing topic raises an error. An advertised
topic with no data times out (default 5000 ms), so reserved topics do not
hang the prompt indefinitely. High display rates add serial and formatting
work; allowed display rates are 0.1..10 Hz. Topic age and validity should
be checked by real consumers independently of listener output.

The console is still Python: use `await listener('imu_sample')`, not the
PX4 shell syntax `listener imu_sample`.
The [console reference](console-tools.md) documents all arguments and fields.

## Adding a new message and task

Create `firmware/messages/temperature.py`:

```python
from message_bus import MessageDef

TEMPERATURE = MessageDef('Temperature', (
    ('sample_time_us', 'u', 0),
    ('temperature_c', 'f', 0.0),
    ('valid', 'b', False),
    ('simulated', 'b', False),
))
```

Import it from `firmware/messages/__init__.py` and `firmware/robot.py`, then register it in
`robot._setup_messages()` before tasks are constructed:

```python
bus.advertise('temperature', TEMPERATURE)
```

A short publisher step may reuse its dict:

```python
payload = TEMPERATURE.new(simulated=True)
topic = bus.topic('temperature')

def step():
    payload['sample_time_us'] = bus.clock.now_us()
    payload['temperature_c'] = 25.0
    payload['valid'] = True
    topic.publish(payload, source_id=4)
```

A consumer owns its subscription and receive dict:

```python
subscription = bus.subscribe('temperature')
sample = {}

def consumer_step():
    if subscription.read_into(sample) and sample['valid']:
        # Use the new sample; no waiting, sleeping or blocking I/O here.
        pass
```

Add step callbacks to `robot.CALLBACKS` and their rates to
`robot.FREQUENCIES_HZ`. Construct per-run task state in `_setup_messages()`
and close subscriptions during shutdown. `firmware/example_task.py` demonstrates
the complete subscribe/process/publish pattern using the virtual IMU.
Add any new task module filename to the firmware list in `tools/upload.ps1`;
Python definition files under `firmware/messages/` are uploaded automatically.
The uploader changes into firmware/ before copying, preserving root-level
imports on the board. Repository folders such as tools/ and tests/ are not
installed on the ESP32.

Increase schema versions when changing contracts. The bus rejects attempts
to advertise an existing name/instance with a conflicting definition.
No bus-internal edits are required for new scalar message types.

## Future optional logging

No logger or transport is created or scheduled currently. `robot_status`
reports storage_available=False and logger_enabled=False. When storage
exists, an SD logger or Raspberry Pi transport can subscribe to selected
topics using bounded buffering. Full-rate recordings need sufficient
queued retention and throughput; a latest-sample subscriber does not
guarantee complete recording. Storage must not block control callbacks.

Next: [Trace and timeline →](tracing.md)
