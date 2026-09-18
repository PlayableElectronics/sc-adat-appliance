#!/usr/bin/env python3
"""Non-transmitting U17 application-loader planning skeleton.

This module deliberately has no serial, USB, socket, or GPIO code. It models
only the instruction-level constraints recovered from the U17 ROM so that a
future capture-backed transport can be added without guessing a wire format.
"""
from __future__ import annotations

from dataclasses import dataclass

LOAD_BASE = 0x8000
VALIDATION_END = 0xFDFD
METADATA_BASE = 0xFDFC
BLOCK_SIZE = 0x80
MAX_IMAGE_SIZE = VALIDATION_END - LOAD_BASE + 1


@dataclass(frozen=True)
class BlockPlan:
    block: int
    address: int
    data: bytes


@dataclass(frozen=True)
class LoadPlan:
    image_size: int
    checksum16_complement: int
    blocks: tuple[BlockPlan, ...]
    entry_point: int = LOAD_BASE


def complemented_sum16(data: bytes) -> int:
    """Return the observed U17-style one's-complement 16-bit byte sum."""
    return (~sum(data)) & 0xFFFF


def make_plan(image: bytes, *, block_size: int = BLOCK_SIZE) -> LoadPlan:
    """Create a local plan; this function performs no I/O beyond its argument."""
    if not image:
        raise ValueError("application image must not be empty")
    if len(image) > MAX_IMAGE_SIZE:
        raise ValueError(f"image exceeds U17 validation span ({MAX_IMAGE_SIZE} bytes)")
    if block_size != BLOCK_SIZE:
        raise ValueError("only the instruction-supported 0x80-byte candidate is allowed")
    blocks = tuple(
        BlockPlan(block=i, address=LOAD_BASE + i * block_size,
                  data=image[offset:offset + block_size])
        for i, offset in enumerate(range(0, len(image), block_size))
    )
    return LoadPlan(len(image), complemented_sum16(image), blocks)


def describe(plan: LoadPlan) -> str:
    """Render an auditable plan without encoding or transmitting a protocol."""
    return (f"entry=0x{plan.entry_point:04X} size={plan.image_size} "
            f"blocks={len(plan.blocks)} checksum16=0x{plan.checksum16_complement:04X} "
            "transport=UNIMPLEMENTED")


if __name__ == "__main__":
    raise SystemExit("planning library only; no transmitting loader is implemented")
