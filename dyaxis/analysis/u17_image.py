#!/usr/bin/env python3
"""Offline builder/validator for the U17 external application image.

This module never opens a serial device and never writes a source dump.  The
builder requires a separately supplied trampoline/template image and copies
its protected FE00..FFFF file window byte-for-byte.
"""
from __future__ import annotations

import argparse
from pathlib import Path

IMAGE_SIZE = 0x8000
PAYLOAD_MAX = 0x7DFC       # file 0000..7DFB; signature begins at 7DFC
SIGNATURE_OFFSET = 0x7DFC
CHECKSUM_OFFSET = 0x7DFE
CHECKSUM_END_EXCLUSIVE = 0x7DFD  # file 0000..7DFC; CPU 8000..FDFC
TRAMPOLINE_OFFSET = 0x7E00
SIGNATURE = b"\xAA\x55"


def checksum(image: bytes) -> int:
    return (~(sum(image[:CHECKSUM_END_EXCLUSIVE]) & 0xFFFF)) & 0xFFFF


def validate(image: bytes) -> list[str]:
    errors = []
    if len(image) != IMAGE_SIZE:
        errors.append(f"size {len(image)} != {IMAGE_SIZE}")
        return errors
    if image[SIGNATURE_OFFSET:SIGNATURE_OFFSET + 2] != SIGNATURE:
        errors.append("signature at CPU FDFC/FDFD is not AA55")
    stored = int.from_bytes(image[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2], "big")
    expected = checksum(image)
    if stored != expected:
        errors.append(f"checksum 0x{stored:04X} != expected 0x{expected:04X}")
    return errors


def build(payload: bytes, template: bytes) -> bytes:
    if len(payload) > PAYLOAD_MAX:
        raise ValueError(f"payload exceeds {PAYLOAD_MAX} bytes")
    if len(template) != IMAGE_SIZE:
        raise ValueError("template must be exactly 32768 bytes")
    image = bytearray(IMAGE_SIZE)
    image[:len(payload)] = payload
    image[SIGNATURE_OFFSET:SIGNATURE_OFFSET + 2] = SIGNATURE
    image[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum(image).to_bytes(2, "big")
    image[TRAMPOLINE_OFFSET:] = template[TRAMPOLINE_OFFSET:]
    return bytes(image)


def main() -> None:
    ap = argparse.ArgumentParser(description="offline U17 image validator/builder")
    sub = ap.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate")
    v.add_argument("image", type=Path)
    b = sub.add_parser("build")
    b.add_argument("payload", type=Path)
    b.add_argument("trampoline_template", type=Path)
    b.add_argument("output", type=Path)
    args = ap.parse_args()
    if args.command == "validate":
        errors = validate(args.image.read_bytes())
        if errors:
            for error in errors:
                print(f"INVALID: {error}")
            raise SystemExit(1)
        print("VALID: signature and complemented big-endian checksum")
    else:
        output = build(args.payload.read_bytes(), args.trampoline_template.read_bytes())
        args.output.write_bytes(output)
        errors = validate(output)
        if errors:
            raise SystemExit("builder produced invalid image: " + "; ".join(errors))
        print(f"WROTE {len(output)} bytes")


if __name__ == "__main__":
    main()
