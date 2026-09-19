# U17 analysis task audit

This checklist audits the U17 deep-analysis deliverables added after the
corrective architecture documentation. It distinguishes static completion
from questions that require hardware evidence.

| Area | Status | Evidence / remaining boundary |
|---|---|---|
| P80C552-aware vector disassembly | Complete | `generated/u17/u17.reachable.asm`, all configured vector entries, 1,830 valid instruction records with ROM-derived exact addresses |
| Reachable function/call inventory | Complete | Existing `functions.tsv`/`call-graph.tsv`; 146 discovered function labels and 71 call/jump callers |
| Literal XDATA and external CODE separation | Complete | Exact-address `u17-xdata-xrefs.tsv`, conservative unknown-DPTR table, and `u17-external-code-dependencies.tsv`; external bodies remain unavailable |
| Indirect/table references | Partial | `u17-indirect-targets.tsv` records 13 valid references; targets are not promoted without data-flow or bus evidence |
| Reset/startup state machine | Partial | Ordered ROM path is documented through service initialization and the `FFE1` wait; external service implementations are unresolved |
| FFE1/FFE3 values and effects | Partial | `u17-state-transitions.tsv` captures static state predicates and effects; decoded hardware ownership is unknown |
| Z85230/host protocol | Partial | Vector shim and FE-page dependencies are confirmed; channel, framing, baud and wire ownership are unresolved |
| Standalone display/fader/LED behavior | Partial | Console behavior is confirmed by observation; U17-local ownership of each visible function is not proven |
| PAL/FPGA architecture | Partial | XC3030/PAL markings and conservative role split are documented; PAL equations, nets and configuration source are unknown |
| FPGA-area socketed programmable devices | Unresolved | Exact identities and mapping to external CODE/configuration targets remain unknown; U13/U14 are differential-interface devices, not ROM candidates |
| Reproducibility | Complete | `run_u17_analysis.sh`, `deep_u17_analysis.py`, tracked ROM, and stdlib regression tests reproduce the reports |

The analysis does not claim that U17 is the entire executable system. It is the
strongest system-leader candidate and contains the main boot/supervisory
firmware, while external CODE targets and other local storage remain open.
