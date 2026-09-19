#!/usr/bin/env python3
"""Independent transcription of U17 02CD..03A3 checksum arithmetic.

This intentionally does not import u17_checksum_emulator.py. It follows the
instruction table in U17_CHECKSUM_INSTRUCTION_TABLE.md directly.
"""
from __future__ import annotations

IMAGE_SIZE = 0x8000
START = 0x8000
END_EXCLUSIVE = 0xFDFD


def complemented_sum(image: bytes) -> int:
    if len(image) != IMAGE_SIZE:
        raise ValueError("image must be exactly 32768 bytes")
    low = 0
    high = 0
    address = START
    while address < END_EXCLUSIVE:
        total = low + image[address - START]
        carry = 1 if total > 0xFF else 0
        low = total & 0xFF
        high = (high + carry) & 0xFF
        address += 1
    low = (~low) & 0xFF
    high = (~high) & 0xFF
    return (high << 8) | low


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    print(f"0x{complemented_sum(args.image.read_bytes()):04X}")
