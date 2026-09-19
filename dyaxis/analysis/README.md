# Reproducible U17 analysis

The U17 image is verified before analysis by `disassemble_u17.sh`. The
control-flow-aware disassembler is `disasm51` 1.0.2 from pinned source commit
`a32d0adc80cfbf203745318900ced5ea94303b15` of
[`OlekMazur/disasm51`](https://github.com/OlekMazur/disasm51). It is used with
all P80C552 interrupt-vector entries and the exact local `p80c552.mcu` SFR and
vector definition.

```sh
./dyaxis/analysis/reproduce_u17.sh
```

That one command creates `.local/disasm51-venv` when needed, installs the
exact pinned disasm51 commit, verifies the installed commit, regenerates all
artifacts and runs the analyzer regression tests. It fails clearly if the
dependency cannot be installed or the requested commit is not present.

The tracked assembly and reports are derived artifacts. They do not replace,
rewrite, or normalize the canonical ROM.

`run_u17_analysis.sh` runs the pinned control-flow disassembly, the existing
P80C552 vector/SFR report, and `deep_u17_analysis.py`. The latter emits
machine-readable exact-address XDATA cross-references, unknown-DPTR records,
external-CODE ABI context, MOVC table records, referenced/candidate string
inventories, state transitions and coverage JSON, plus the generated U17
reports in `generated/u17/`. Literal XDATA accesses are tracked separately
from external CODE calls; no high address is silently treated as a register
or as executable code.

The deep pass can be reproduced directly from tracked files:

```sh
python3 dyaxis/analysis/deep_u17_analysis.py \
  dyaxis/analysis/generated/u17/u17.reachable.asm \
  dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin \
  dyaxis/analysis/generated/u17
```

The generated assembly is a reachable instruction map from all P80C552 vector
entries. The deep artifacts reconstruct exact instruction addresses from the
ROM and 8051 opcode lengths; any unresolved/merged DPTR state is explicitly
excluded from claimed XDATA references.

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
