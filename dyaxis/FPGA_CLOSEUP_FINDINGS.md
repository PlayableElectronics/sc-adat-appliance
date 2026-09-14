# FPGA-area close-up findings

Photos: `photo/fpga/2700.jpg`, `2702.jpg`, `2703.jpg`.

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

## Dumping priorities

1. Photograph every label and orientation mark one more time.
2. Record the exact package/device marking under each label if visible at the
   package edge.
3. Dump both ROMs with a programmer that supports the exact device family;
   read each twice and compare hashes.
4. If possible, read the PAL using a compatible programmer or first identify
   whether it is protected. Never attempt a write or erase operation.
5. Map the ROM address/data/control traces to the P80C552 and XC3030 before
   interpreting either dump.
