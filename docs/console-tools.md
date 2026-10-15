# Console tools

[Handbook](README.md) · [Contents](SUMMARY.md)

Use these commands at `robot>`, not PowerShell or the native `>>>` prompt.
This is a Python console; the PX4 shell spelling `listener imu_sample` is
not supported. Use `await listener('imu_sample')`.

## topics: identify available data

```python
await topics()
await topics('task_performance')
```

`topics(name=None)` lists all instances, or only an exact topic name.
Each task-performance row includes a registered identity, even before its
first message is published. Example output (counters are illustrative):

```text
topic[instance] (identity)                  schema v  depth  sequence  subs
task_performance[0] (motor)                 TaskPerformance v1  1  42  0
task_performance[1] (speed_brake)           TaskPerformance v1  1  42  0
task_performance[7] (virtual_imu)           TaskPerformance v1  1  42  0
```

| Column | Meaning |
| --- | --- |
| topic[instance] | Topic name and independent instance number |
| identity in parentheses | Human-readable identity; for performance, the task name |
| schema v | Message type and version |
| depth | Number of retained samples, not number of tasks |
| sequence | Cumulative publications for this topic instance; not Hz |
| subs | Currently open subscriptions, not historical readers |

There is one performance instance per scheduled task, not an extra monitoring
task per row. Each needs its own latest sample. `manual_input` and
`velocity_setpoint` currently have no publishers, so sequence 0 is expected.
After closing top/listener, their subscriptions should disappear; the example
task normally remains subscribed to `imu_sample`.

## listener: print topic data

```python
await listener('imu_sample', count=3)
await listener('task_performance', instance='motor', count=3)
await listener('task_performance', instance='virtual_imu', count=1)
await listener('task_performance', instance=7, count=1)
await listener('bus_status', count=1)
```

Prefer identity labels when available: they avoid relying on numeric task
positions that may change when callbacks are added or reordered. Numeric
selectors remain supported. Named selectors resolve the topic's registered
label, not its latest payload; ambiguous or missing labels raise an error.

Signature:

```python
await listener(name, instance=0, count=None, rate_hz=2, timeout_ms=5000)
```

| Argument | Default | Behavior |
| --- | --- | --- |
| name | Required | Exact advertised topic name |
| instance | 0 | Nonnegative instance number or identity label |
| count | None | Print continuously; a positive integer stops after that many samples |
| rate_hz | 2 | Maximum requested display rate, allowed 0.1..10 Hz |
| timeout_ms | 5000 | Exit after no new data, allowed 1..60000 ms |

Output/formatting time also limits display rate. A slow latest-sample listener
intentionally skips intermediate publications; `missed` counts those gaps.
It does not lower the producer's configured rate or consume data away from
another subscriber. An advertised, unpublished topic times out gracefully.

Ctrl+C stops only the listener and releases its subscription. The header
identifies the selected instance, and payload fields include the timestamp,
sequence, schema version, source and session identifiers.

## top: monitor task frequencies

```python
await robot.top()
await robot.top(refresh_ms=2000)
await robot.top(samples=5, clear=False)
```

Signature: `await robot.top(refresh_ms=1000, samples=None, clear=True)`.
Refresh must be at least 250 ms. `samples` limits the number of screens;
`clear=False` appends screens for terminal logs. Ctrl+C closes only top.
There may be a wait for the first diagnostics publications after startup.

| Field | Meaning |
| --- | --- |
| target | Configured task rate in Hz |
| live_Hz | Measured executions per second in the message's window |
| runs, skip | Completed steps and skipped scheduled releases in that window |
| avg_us | Average callback duration in that window |
| max_us, errors | Maximum duration and cumulative errors for the session |
| age_ms | Time since that performance sample was published |

Top subscribes to performance topics. Each is updated about once a second,
with slightly different measurement windows because publication work is
spread across middleware steps. Increasing screen refresh rate does not
increase the producer's diagnostic publication rate.

## Other robot commands

| Command | Where | Purpose |
| --- | --- | --- |
| `robot.report()` | robot> or >>> after a run | Session statistics snapshot |
| `robot.imu_scenario('stationary')` | robot> | Level sensor, zero angular rate |
| `robot.imu_scenario('rotation')` | robot> | Constant yaw rate, +0.5 rad/s |
| `robot.imu_scenario('oscillation')` | robot> | Sinusoidal roll and consistent IMU data |
| `robot.console()` | Native >>> | Start tasks with async prompt; new session |
| `robot.run(duration_ms=5000)` | Native >>> | Run without async console, then stop |
| `robot.capture(5000, capacity=4096)` | Native >>> | Run a timed execution trace |
| `robot.timeline(40)` | Native >>> after capture | Print the first 40 recorded steps |
| `robot.save_trace('trace.json')` | Native >>> after capture | Save recorded events on ESP32 |

`robot.topics()` and `robot.listener()` are equivalent to the short console
aliases. New runs clear previous statistics and traces. See
[Trace and timeline](tracing.md) before starting a capture.

## Timing impact

These are diagnostic tools, not transparent background observers. Compiling
Python commands, serial output, formatting and garbage collection can delay
cooperative tasks. Writes are paced to reduce UART buffering stalls, but
rates may fall while actively interacting. Check skipped slots and sample
age, and measure actual control workload separately.

Next: [Tasks and scheduling →](tasks.md)
