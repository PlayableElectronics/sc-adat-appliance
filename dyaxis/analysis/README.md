# Reproducible U17 analysis

The U17 image is verified before analysis by `disassemble_u17.sh`. The
control-flow-aware disassembler is `disasm51` 1.0.2 from pinned source commit
`a32d0adc80cfbf203745318900ced5ea94303b15` of
[`OlekMazur/disasm51`](https://github.com/OlekMazur/disasm51). It is used with
all P80C552 interrupt-vector entries and the exact local `p80c552.mcu` SFR and
vector definition.

```sh
python3 -m venv .local/disasm51-venv
.local/disasm51-venv/bin/python -m pip install --no-deps \
  'git+https://github.com/OlekMazur/disasm51@a32d0adc80cfbf203745318900ced5ea94303b15'
./dyaxis/analysis/run_u17_analysis.sh
python3 -m unittest dyaxis.analysis.test_deep_u17_analysis
```

The tracked assembly and reports are derived artifacts. They do not replace,
rewrite, or normalize the canonical ROM.

`run_u17_analysis.sh` runs the pinned control-flow disassembly, the existing
P80C552 vector/SFR report, and `deep_u17_analysis.py`. The latter emits
machine-readable XDATA cross-references, external-CODE dependencies, indirect
references, string inventory, state transitions and a classification JSON file,
plus the six generated U17 reports in `generated/u17/`. Literal XDATA accesses
are tracked separately from external CODE calls; no high address is silently
treated as a register or as executable code.

The deep pass can be reproduced directly from tracked files:

```sh
python3 dyaxis/analysis/deep_u17_analysis.py \
  dyaxis/analysis/generated/u17/u17.reachable.asm \
  dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin \
  dyaxis/analysis/generated/u17
```

The generated assembly is a reachable instruction map from all P80C552 vector
entries. The disassembler output does not annotate every instruction with a
numeric address, so generated tables identify a valid instruction by its
containing function and ordinal when an exact byte offset is unavailable.

The U17 main-program reconstruction and high-address service-register map are in:

- `U17_MAIN_PROGRAM_ARCHITECTURE.md`
- `U17_HIGH_ADDRESS_MAILBOX.md`
- `generated/u17/U17_COMPLETE_PROGRAM_MAP.md`
- `generated/u17/U17_STARTUP_STATE_MACHINE.md`
- `generated/u17/U17_EXTERNAL_CODE_DEPENDENCIES.md`
- `generated/u17/U17_SERVICE_WINDOW.md`
- `generated/u17/U17_SERIAL_AND_HOST_PROTOCOL.md`
- `generated/u17/U17_STANDALONE_CAPABILITIES.md`

The six generated reports intentionally retain unresolved external CODE,
indirect dispatch, host framing and hardware ownership questions. The next
highest-value passive observations are listed in `U17_UNRESOLVED_OBSERVATIONS.md`.
The completed/partial/unresolved task audit is `U17_TASK_AUDIT.md`.
