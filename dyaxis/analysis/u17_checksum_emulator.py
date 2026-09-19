#!/usr/bin/env python3
"""Small instruction-level model of U17 startup validation/checksum paths.

It models the exact operations visible at U17 02CD..0311 and 037C..03A3.
It intentionally treats the supplied image as an XDATA image at CPU 8000,
and reports that mapping assumption instead of hiding it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

IMAGE_SIZE = 0x8000
XDATA_BASE = 0x8000


def xdata_read(image: bytes, address: int) -> int:
    if not 0x8000 <= address <= 0xFFFF:
        raise ValueError(f"unsupported XDATA address 0x{address:04X}")
    return image[address - XDATA_BASE]


def checksum_037c(image: bytes):
    # 037C: R4:R5 receives the exclusive endpoint, then R4:R5 is cleared.
    end_hi, end_lo = 0xFD, 0xFD
    r4, r5 = 0, 0
    r6, r7 = 0x80, 0x00
    reads = []
    while True:
        # SETB C; SUBB A,R5; MOV A,R6; SUBB A,R4; JNC 039D.
        low_difference = r7 - end_lo
        borrow = int(low_difference < 0)
        high_difference = r6 - end_hi - borrow
        if high_difference >= 0:
            break
        address = (r6 << 8) | r7
        value = xdata_read(image, address)
        reads.append({"cpu_address": f"0x{address:04X}", "file_offset": f"0x{address - XDATA_BASE:04X}", "value": value})
        total = value + r5
        carry = int(total > 0xFF)
        r5 = total & 0xFF
        r4 = (r4 + carry) & 0xFF  # ADDC A,R4 with A cleared
        r7 = (r7 + 1) & 0xFF
        if r7 == 0:
            r6 = (r6 + 1) & 0xFF
    result_r7 = (~r5) & 0xFF
    result_r6 = (~r4) & 0xFF
    return {
        "start_cpu": "0x8000", "end_exclusive_cpu": "0xFDFD",
        "end_inclusive_cpu": "0xFDFC", "start_file": "0x0000",
        "end_inclusive_file": "0x7DFC", "reads": reads,
        "read_count": len(reads), "r4": r4, "r5": r5,
        "result_r4_r5_before_return": f"0x{r4:02X}{r5:02X}",
        "result_r6_r7": f"0x{result_r6:02X}{result_r7:02X}",
        "complement": (result_r6 << 8) | result_r7,
    }


def startup_validation(image: bytes):
    if len(image) != IMAGE_SIZE:
        raise ValueError("image must be exactly 32768 bytes")
    first_hi = xdata_read(image, 0xFDFE)
    first_lo = xdata_read(image, 0xFDFF)
    marker1_ok = (first_hi, first_lo) == (0xAA, 0x55)
    second_hi = xdata_read(image, 0xFDFC)
    second_lo = xdata_read(image, 0xFDFD)
    marker2_ok = (second_hi, second_lo) == (0xAA, 0x55)
    if not marker1_ok:
        branch = "0x029C -> 0x02A1 -> 0x02CD"
    elif not marker2_ok:
        branch = "0x02A9 -> 0x02CD"
    else:
        branch = "0x02AC -> 0x30A7 (wait path; checksum routine not called here)"
    checksum = checksum_037c(image)
    stored_hi = xdata_read(image, 0xFDFE)
    stored_lo = xdata_read(image, 0xFDFF)
    stored = (stored_hi << 8) | stored_lo
    return {
        "mapping": "file_offset = CPU_XDATA_address - 0x8000",
        "marker_fdfE_fdff": {"bytes": f"{first_hi:02X}{first_lo:02X}", "matches_AA55": marker1_ok},
        "marker_fdfc_fdfd": {"bytes": f"{second_hi:02X}{second_lo:02X}", "matches_AA55": marker2_ok},
        "branch": branch, "failure_message": not (marker1_ok and marker2_ok),
        "checksum": checksum, "stored_checksum_read_at_fdfE_fdff": f"0x{stored:04X}",
        "stored_checksum_matches": stored == checksum["complement"],
    }


def analyze(path: Path):
    image = path.read_bytes()
    result = startup_validation(image)
    result["path"] = path.name
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = analyze(args.image)
    text = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
