"""Consistent ideal sensor motion, not full spherical-robot physics."""
import math
from messages import IMU_SAMPLE, SIMULATION_STATE


class VirtualIMU:
    SCENARIOS = ("stationary", "rotation", "oscillation")

    def __init__(self, bus):
        self.bus = bus
        self.imu_topic = bus.topic("imu_sample")
        self.state_topic = bus.topic("simulation_state")
        self.sample = IMU_SAMPLE.new(simulated=True, valid_flags=3)
        self.state = SIMULATION_STATE.new()
        self.set_scenario("stationary")

    def set_scenario(self, scenario):
        if scenario not in self.SCENARIOS:
            raise ValueError("Choose stationary, rotation or oscillation")
        self.scenario = scenario
        self.origin = self.bus.clock.now_us()
        self.next_state = self.origin

    def step(self):
        now = self.bus.clock.now_us()
        t = (now - self.origin) / 1_000_000
        roll = yaw = wx = wz = 0.0
        if self.scenario == "rotation":
            wz = 0.5
            yaw = (wz * t) % (2 * math.pi)
        elif self.scenario == "oscillation":
            phase = 2 * math.pi * 0.5 * t
            roll = 0.25 * math.sin(phase)
            wx = 0.25 * 2 * math.pi * 0.5 * math.cos(phase)
        sample = self.sample
        sample["sample_time_us"] = now
        sample["accel_y"] = 9.80665 * math.sin(roll)
        sample["accel_z"] = 9.80665 * math.cos(roll)
        sample["gyro_x"], sample["gyro_z"] = wx, wz
        self.imu_topic.publish(sample, source_id=1)
        if now >= self.next_state:
            state = self.state
            state["sample_time_us"], state["scenario"] = now, self.scenario
            state["q_w"], state["q_x"] = math.cos(roll / 2) * math.cos(yaw / 2), math.sin(roll / 2)
            state["q_y"], state["q_z"] = 0.0, math.sin(yaw / 2)
            state["omega_x"], state["omega_z"] = wx, wz
            self.state_topic.publish(state, source_id=1)
            self.next_state += 50_000
            if self.next_state <= now:
                self.next_state += ((now - self.next_state) // 50_000 + 1) * 50_000
