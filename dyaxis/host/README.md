# Future U17 host-loader boundary

`u17_loader_skeleton.py` is intentionally non-transmitting. It accepts an
application image supplied by a caller and creates a local, auditable plan
using the instruction-level U17 constraints:

- entry at `0x8000`;
- candidate `0x80`-byte blocks;
- complemented 16-bit sum over the image/validation span;
- no serial, USB, socket or GPIO access.

The actual packet encoder, register transport and metadata layout must be
implemented only after a passive capture proves them. The replacement
application ABI is documented in `../analysis/U17_EXECUTABLE_RAM_LOADING.md`.
