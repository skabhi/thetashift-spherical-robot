"""Copy this pattern when adding a task that subscribes and publishes.

Register its output schema/topic in setup, and schedule step() in robot.py.
Never wait, print a screen, or perform blocking I/O in a step callback.
"""
import math
from messages import IMU_SUMMARY


class ExampleTask:
    def __init__(self, bus):
        self.bus = bus
        self.input = bus.subscribe("imu_sample")
        self.output = bus.topic("imu_summary")
        self.sample = {}
        self.result = IMU_SUMMARY.new()

    def step(self):
        # Each subscription has its own cursor: other consumers still see it.
        if not self.input.read_into(self.sample):
            return
        sample, result = self.sample, self.result
        result["sample_time_us"] = sample["sample_time_us"]
        result["input_sequence"] = sample["sequence"]
        ax, ay, az = sample["accel_x"], sample["accel_y"], sample["accel_z"]
        gx, gy, gz = sample["gyro_x"], sample["gyro_y"], sample["gyro_z"]
        result["accel_magnitude"] = math.sqrt(ax * ax + ay * ay + az * az)
        result["gyro_magnitude"] = math.sqrt(gx * gx + gy * gy + gz * gz)
        result["valid"] = sample["valid_flags"] == 3
        result["simulated"] = sample["simulated"]
        self.output.publish(result, source_id=2)

    def close(self):
        self.input.close()
