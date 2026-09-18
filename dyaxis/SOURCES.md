# Research sources

Collected 2026-09-06. Links are retained because many Dyaxis documents are
only available as scans or archived magazine pages.

## Most useful sources

- GroupDIY: [Studer Dyaxis II service manual thread](https://groupdiy.com/threads/studer-dyaxis-ii-sevice-manual.79464/). A 2022 owner specifically planned a MIDI/USB conversion and identifies the controller interfaces as **RS-422 and ADB for keyboard and trackball**. A reply points to Alan's Dyaxis engineering page at `https://magicsound.us/dyaxis2.html`. This is the strongest direct lead for the controller electronics, but it is forum testimony, not a service manual.
- Mix, September 1994: [Dyaxis II MultiMix review](https://www.worldradiohistory.com/Archive-All-Audio/Mix-Magazine/90s/94/Mix-1994-09.pdf). Describes the MultiDesk/MultiMix control surface: eight faders in two banks of four, four assignable knobs/shaft encoders, fourteen soft switches, per-channel input/repro/solo/EQ/mute/automation buttons, transport controls, scrub/shuttle wheel, standard Kensington trackball through ADB, and a QWERTY keyboard connected to the host Macintosh through ADB. It also mentions an additional controller port for an optional MultiMeter panel.
- Radio World, February 1996: [Dyaxis II user report](https://manuals.plus/m/57bc843cdc3a82f8587acf6f9381c06e99dd7ce822a27d129890c2e6cab08924.pdf). Confirms the MultiDesk as a physical button-based alternative to the computer UI, and describes Input/Repro/Record Ready buttons for each track, four XLR outputs, DSP/mixer automation and AES/EBU use.
- Reverb listing: [complete Dyaxis I/II system with remote controller](https://reverb.com/item/93152098-studer-dyaxis-i-ii-digital-audio-editing-system-apple-macintosh-iix-complete-rare-vintage-set). Useful visual/reference evidence for identifying the controller variant and associated rack units. Treat seller descriptions as unverified.
- Sound On Sound, May 1990: [Studer Dyaxis review](https://www.muzines.co.uk/articles/studer-dyaxis/5815). Documents first-generation system architecture: Macintosh host, audio processor rack, optional timecode, SCSI hard disks, analog/digital processor variants, and DSP option. It lists the original digital formats and confirms that the controller was primarily a computer-facing interface.
- Mix, May 1990: [Dyaxis field test](https://device.report/m/361e84013793b0f48d7a2210d0f462084f0d89177030f80f358e8164dc9c8383.pdf). Contemporary overview of the processor/rack and Macintosh-based MacMix system.
- World Radio History, January 1990: [Studer/Editech Swiss Sound issue](https://www.reeltoreel.nl/studer/Public/SwissSound/SwissSound28eJan90LR.pdf). Establishes the Studer acquisition of IMS/Editech and the contemporary Dyaxis product context.

## Additional historical leads

- [Studio Sound 1989-08](https://www.worldradiohistory.com/Archive-All-Audio/Archive-Recording-Engineer/Archive-Studio-Sound/80s/Studio-Sound-1989-08.pdf) reports an Abekas controller/trackball interface and a Motorola 56000-based DSP card under development.
- [Music Technology 1989-07](https://worldradiohistory.com/UK/Music-Technology/Music-Technologyy-1989-07.pdf) mentions MacMix 2.0, keyboard macros, timecode, and Abekas controller-panel/trackball control.
- [Studio Sound 1990-11](https://www.worldradiohistory.com/Archive-All-Audio/Archive-Recording-Engineer/Archive-Studio-Sound/90s/Studio-Sound-1990-11.pdf) discusses Dyaxis backup and SCSI-era system details.
- [Studer D19 MIDI manual](https://www.manualslib.com/manual/3550642/Studer-D19-Series.html?page=37) is not a Dyaxis controller document, but is useful Studer-era reference material for MIDI electrical conventions and remote-control thinking. Do not assume its protocol applies to Dyaxis.

## Component references

- [NXP/Philips 80C552 datasheet](https://www.nxp.com/docs/en/data-sheet/80C552_83C552.pdf). The photographed P80C552 is an 80C51-family MCU with 10-bit ADC, capture/compare timer, high-speed outputs, dual PWM, I²C, UART and parallel I/O. This makes it capable of scanning analog faders/knobs and driving timing-sensitive peripherals without an external modern MCU.
- [Philips 8XC552/562 overview](https://www.keil.com/dd/docs/datashts/philips/8xc5x2_ov.pdf). Used for the P80C552-specific SFR map, the 15 interrupt vectors, and the distinction between SIO0 UART and SIO1 I²C in the U17 analysis. Generic 8051 SFR names are not treated as U17 findings unless they occur at a valid disassembled instruction boundary.
- [Zilog Z85230 ESCC product brief](https://zilog.com/docs/serial/z85230pb.pdf). The photographed Z85230-family device is a dual-channel full-duplex multiprotocol controller with baud generators, DPLL, async/sync modes and CRC/HDLC/SDLC support. It is a strong candidate for the controller's host/inter-board serial subsystem, but the actual physical RS-485 transceiver must still be located and identified.
- [Xilinx XC3000-series FPGA documentation](https://media.digikey.com/pdf/data%20sheets/xilinx%20pdfs/xc3000%20series.pdf). The photographed XC3030 is from the early XC3000 family: a 5 V, SRAM-configured FPGA with roughly 2,000 effective gates and 68-pin PLCC variants. Its configuration source and power-on loading path are important preservation targets; do not assume the FPGA retains its design without external configuration data.

## What is still missing

No public service manual, schematic, connector pinout, ROM image or verified
Dyaxis controller protocol has been located yet. The GroupDIY reference to
RS-422 and ADB is a lead to test, not proof for this exact unit. Search terms
to continue: `Dyaxis MultiDesk`, `Dyaxis MultiMix`, `Dyaxis Edit Controller`,
`Studer Editech controller`, `Dyaxis ADB`, `Dyaxis RS422`, and the exact PCB
part numbers once photographed.
