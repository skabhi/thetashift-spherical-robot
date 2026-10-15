# Troubleshooting

[Handbook](README.md) · [Contents](SUMMARY.md)

## COM6 is busy

Only one program can own the serial port. Press Ctrl+] in an existing
mpremote session, or close the Serial Monitor/IDE using COM6. Retry the
uploader or connection command. Substitute the actual port shown by
`py -m mpremote connect list` if your board moved.

## The screen is blank after connecting

Press Enter. A running robot may be quietly waiting at its async prompt.
If the board was left at native `>>>`, use `import robot; robot.console()`.
If startup failed, inspect the error; avoid sending Ctrl+C while boot-time
imports are still running, because that can interrupt startup.

## await gives a syntax error

You may be at native `>>>`. Start `robot.console()` first, then issue the
awaited tool at `robot>`. Conversely, stop the async console with Ctrl+D
before calling `robot.capture()` or `robot.run()`; nested runs are rejected.

## I cannot tell which performance instance is which

Update firmware, then use `await topics('task_performance')`. Identities
such as `(motor)` and `(virtual_imu)` appear on each row. Prefer named
selection: `await listener('task_performance', instance='motor', count=1)`.
If you still see the old header, the new modules have not loaded. Stop the
async console, upload both robot.py and message_bus.py (or use upload.ps1),
and restart. Copying files does not reload an already imported module.

## A topic has sequence 0 or the listener times out

An advertised topic need not have a publisher yet. `manual_input` and
`velocity_setpoint` are reserved. Do not treat their default definitions as
valid commands. Performance samples also take about a second after startup.

## Topic sequences or frequencies differ slightly

Sequence is a cumulative publication count, not frequency. `topics()`
prints rows over time while publishers continue running; the list is not a
frozen snapshot. Performance updates are spread across middleware steps.
Short windows and session boundaries also affect measured Hz.

## subs stays at 1 for imu_sample

The example task is an active subscriber. Top and listener release their
own subscriptions on exit; they do not close the example's subscription.
Reading a topic does not remove data from other subscribers.

## missed is large in listener

A 2 Hz preview of a 100 Hz latest-sample topic necessarily omits most
samples. This is expected. It differs from skipped task releases and from
unread queued-event evictions. See [Messages](messages.md) for the counters.

## Rates fall while I use the console

Python command compilation, formatting, serial transfer and garbage
collection take time. Tools yield and pace output, but do not offer hard
real-time isolation. Compare normal operation and interactive workloads;
watch skip, errors and age_ms. Avoid blocking commands or high display rates.

## trace.json is missing or empty

Call capture and save_trace in the same native-REPL session before another
run. Copying it with mpremote saves a second copy on your computer; it does
not create a device trace. Check the reported event count and buffer overflow.
If capture raises MemoryError, reduce capacity or reboot to release memory.

## Import errors after uploading

Run upload.ps1 from the repository. The firmware needs message_bus.py,
virtual_imu.py, example_task.py, robot.py, main.py and the messages package,
plus aiorepl under /lib. New custom task modules must be added to the uploader.

Next: [Tests and measurements →](testing.md)
