# FPGA-area close-up findings

Photos: `photo/fpga/2700.jpg`, `2702.jpg`, `2703.jpg`.

- `2677.jpg` visibly identifies the large device as **XILINX
  XC3030TM-70 PC68C**. The `PC68C` marking identifies the 68-pin plastic
  leaded chip-carrier package; this is not inferred from the body outline.

- `2700.jpg` shows a large socketed AMD/programmable ROM with Studer label
  beginning **41.005.415.71** and a visible **SEC 1994** line. The middle
  revision/application text is partly obscured or soft, so retain the image
  transcription as provisional until a straight-on retake.
- `2702.jpg` shows a second nearby socketed ROM with label beginning
  **41.005.416.70**. This supports the owner's observation that the large
  devices are programmed firmware/configuration parts, not just empty sockets.
- `2703.jpg` clearly identifies a separate programmable logic device:
  **PALC22V10L-25PC**, marking **9353 000020**. This is not an EPROM; it is
  likely board glue/state/address-decoding logic. Preserve it as carefully as
  the ROMs because its programmed contents may be unique.
- The three devices sit in the FPGA/CPU area and should be treated as a
  configuration cluster: XC3030 FPGA + one or more ROMs + PAL logic. We must
  not assume which ROM feeds the FPGA until we trace the FPGA configuration
  pins and inspect power-up traffic.

- The PCB reference designator for the PAL is not legible in the existing
  photographs. Do not invent a U-number. The `PC` ordering suffix identifies
  the 24-pin molded-DIP PAL family from the exact marking/datasheet, not from
  package shape alone.

## Configuration interpretation

The XC3000 family uses volatile SRAM configuration. Xilinx documentation
describes master-serial configuration from an external serial PROM,
master-parallel configuration from a byte-wide EPROM, and peripheral mode in
which a processor supplies configuration data. The visible PAL is therefore
not, by identity, the FPGA configuration source.

The P80C552/U17 ROM could configure the FPGA only if board wiring selects
processor-controlled/peripheral mode and the ROM contains a loader. The U17
disassembly proves neither. Its external `MOVX` and out-of-image calls around
`0xFEC0`–`0xFEF9` must be treated as an address-decoded external
device/window, potentially involving FPGA/PAL glue, not automatically as
another ordinary ROM.

## Dumping priorities

1. Photograph every label and orientation mark one more time.
2. Record the exact package/device marking under each label if visible at the
   package edge.
3. Dump both ROMs with a programmer that supports the exact device family;
   read each twice and compare hashes.
4. Do not read the PAL with an EPROM definition. It is not a configuration
   PROM; any future PAL preservation requires an exact device/programmer
   definition and a separate, read-only workflow.
5. Map the ROM address/data/control traces to the P80C552 and XC3030 before
   interpreting either dump.
