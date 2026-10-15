import asyncio
import machine
import os
from time import ticks_us, ticks_diff

machine.freq(240_000_000)
print(os.uname())
print("CPU_HZ", machine.freq())

async def probe():
    for delay in (0, 1, 5, 9, 10, 11, 20):
        samples = []
        for _ in range(40):
            start = ticks_us()
            await asyncio.sleep_ms(delay)
            samples.append(ticks_diff(ticks_us(), start))
        print("sleep_ms", delay, "min_us", min(samples), "mean_us",
              sum(samples) // len(samples), "max_us", max(samples))

asyncio.run(probe())
