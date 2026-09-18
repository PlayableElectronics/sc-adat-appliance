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
```

The tracked assembly and reports are derived artifacts. They do not replace,
rewrite, or normalize the canonical ROM.
