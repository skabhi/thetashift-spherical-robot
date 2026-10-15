# Tasks and scheduling

[Handbook](README.md) · [Contents](SUMMARY.md)

## Scheduled work

| Task / performance identity | Target Hz | Current behavior |
| --- | ---: | --- |
| motor | 100 | Placeholder; no physical outputs |
| speed_brake | 50 | Placeholder |
| wifi | 1 | Placeholder |
| bluetooth | 20 | Placeholder |
| messages | 50 | Publish task/bus/robot diagnostics in bounded pieces |
| manual | 50 | Placeholder |
| velocity | 50 | Placeholder |
| virtual_imu | 100 | Publish simulated IMU; ground truth approximately 20 Hz |
| example | 20 | Subscribe to IMU and publish vector magnitudes |

The configuration is `FREQUENCIES_HZ` in `robot.py`; implementations are
registered in `CALLBACKS`. Performance identities come directly from those
callback names. Numeric instance IDs are their positions in that registry.

## Runtime organization

```text
main.py -> robot.console() -> asyncio event loop
                              |-- logical task dispatcher
                              |-- async Python console
                              |-- listener or top when requested

virtual IMU -> imu_sample -> example -> imu_summary
middleware -> task_performance -> top or listener
```

A single dispatcher maintains independent deadlines for all logical tasks.
It checks ready callbacks in registry order, executes a short step, and
yields. They are not independent OS threads or priority-preemptive RTOS tasks.

Deadlines advance from previous releases rather than from completion time
to reduce drift. A task that falls behind skips obsolete scheduled releases
instead of running a burst of stale work. Its statistics count those skips.
`TASK_PHASE_US` staggers the IMU, example and middleware work within cycles.

## Why precision waiting exists

On the tested ESP32 firmware, `asyncio.sleep_ms(10)` took approximately
20 ms. This produced missed 100 Hz releases. `_wait_until()` uses normal
sleeps for distant deadlines, and cooperative zero-delay yields during the
last 12 ms. This trades CPU activity and power for better timing precision.
It still has jitter and does not guarantee a maximum control-loop latency.

Callbacks must be synchronous, short and nonblocking. Do not put
`time.sleep()`, a Wi-Fi connection wait, a long calculation or a whole
serial screen inside a step. Future asynchronous network I/O should run in
separate coroutines and exchange data through bounded bus topics.

## Where the bus fits

Publish/subscribe calls update or copy topic data immediately. They do not
wait for the `messages` task to forward messages. That task is periodic
diagnostic housekeeping, not an external broker or network server.

The virtual IMU currently represents a sensor on an internal body at a
fixed pivot. The actual spherical robot's sensor mounting, actuator layout
and physical control strategy remain undecided. Keep those decisions in
drivers/control modules rather than the message bus.

## Lifecycle and faults

`robot.console()` and `robot.run()` create a fresh bus and task statistics.
Normal exit or task failure cancels scheduled work and calls `stop_motors()`.
That function is currently a placeholder: implement physical output shutdown
before adding real motor control. Task exceptions propagate and stop the run.

No logger is created or scheduled. Future SD-card or Raspberry Pi storage
must be optional, buffered and unable to block control steps.

Next: [Messages and task extensions →](messages.md)
