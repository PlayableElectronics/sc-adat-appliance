"""Pure recording-session policy; no audio or JACK operations live here."""
from dataclasses import dataclass

TWO_HOURS = 2 * 60 * 60
EMERGENCY_RESERVE = 5 * 1024**3
CHANNELS = 19  # physical 1..17, plus final stereo master


def bytes_per_second(sample_rate=48000, channels=CHANNELS, bits=24):
    return sample_rate * channels * (bits // 8)


def required_ready_bytes(sample_rate=48000, channels=CHANNELS, bits=24, seconds=TWO_HOURS):
    return bytes_per_second(sample_rate, channels, bits) * seconds


def segment_can_start(free_bytes, segment_seconds=900, sample_rate=48000,
                      channels=CHANNELS, bits=24, reserve=EMERGENCY_RESERVE):
    return free_bytes >= bytes_per_second(sample_rate, channels, bits) * segment_seconds + reserve


def validate_target(mountpoint, expected_uuid, mounted_uuid, writable, filesystem="ext4"):
    if mountpoint != "/recordings":
        return "NO_RECORDING_DISK"
    if not expected_uuid or mounted_uuid != expected_uuid or not writable or filesystem != "ext4":
        return "NO_RECORDING_DISK"
    return "READY"


@dataclass
class RecorderState:
    value: str = "IDLE"
    segment: int = -1
    error: str = ""

    def begin(self):
        if self.value != "READY":
            raise RuntimeError(f"cannot start from {self.value}")
        self.value, self.segment = "RECORDING", 0

    def next_segment(self, free_bytes, segment_seconds=900):
        if self.value != "RECORDING":
            return False
        if not segment_can_start(free_bytes, segment_seconds):
            self.value = "FINAL_SEGMENT"
            return False
        self.segment += 1
        return True

    def space_during_segment(self, free_bytes):
        if free_bytes < EMERGENCY_RESERVE:
            self.value = "STOPPED_FULL"

    def fail(self, reason, disk_lost=False):
        self.value = "DISK_LOST" if disk_lost else "FAILED"
        self.error = str(reason)
