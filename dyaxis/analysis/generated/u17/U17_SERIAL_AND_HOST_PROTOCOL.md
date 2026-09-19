# U17 serial and host-protocol boundary

The SIO0 vector at `0023` reaches `3416`. That ISR reads XDATA `FED0`, loads
PSW from the returned byte, calls external CODE `FED1`, restores context and
returns `RETI`. Related interrupt shims use `FEC0/FEC4/FEC8/FECC/FED8..FEF8`
and adjacent external CODE targets.

U17 contains no reachable direct S0CON/S0BUF/TH1/TMOD setup in this pass.
Therefore framing, buffers, escape bytes, lengths, checksums, command IDs,
Z85230 channel selection and baud remain unproven. Passive capture or an
external-bus trace is required; the local FFE1/FFE3 service window must not be
used as a wire-protocol substitute.
