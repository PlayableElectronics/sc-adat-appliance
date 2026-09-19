# Highest-value unresolved U17 observations

Static analysis now establishes valid U17 instruction boundaries, startup
calls, the `FFE1/FFE3` service-window access pattern, and the external CODE
dependency boundary. It cannot identify the devices behind those buses or
recover code outside the EPROM.

Prioritized, receive-only observations:

1. Capture the P80C552 external bus during reset through the first
   `FFE1/FFE3` service exchange. Record `/PSEN`, `/RD`, `/WR`, address and data
   together. This is the smallest measurement that can distinguish an FPGA/
   peripheral service window from another ROM or RAM and can resolve the
   external CODE calls around `FE00..FEF9`.
2. With power removed, photograph or continuity-trace the two undumped
   socketed ROM candidates and their chip-select/address wiring. Do not remove
   or read either device until its exact marking and a compatible definition
   are established.
3. Passively observe the XC3030/PAL area during startup to determine whether
   the FPGA is configured by a local source and whether PAL decode/control
   strobes correspond to `FFE1/FFE3`. The PALC22V10 is a PLD; its equations and
   any stateful role remain unknown.
4. Only after the controller’s rear transceivers and pairs are identified,
   capture both RS-422 receive directions without transmission. U17 alone does
   not prove channel ownership, baud, framing, or host semantics.

These measurements are deliberately narrower than a general bus or protocol
reverse-engineering campaign. No active probe is justified by the current ROM
evidence.
