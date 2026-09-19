# U17 serial and host-protocol boundary

The SIO0 vector at `0023` reaches `3416`. That ISR reads XDATA `FED0`, loads
PSW from the returned byte, calls external CODE `FED1`, restores context and
returns `RETI`. The FE-page call-site ABI table is `u17-fe-abi.tsv`.

U17 contains no reachable direct S0CON/S0BUF/TH1/TMOD setup in this pass.
Framing, buffers, escape bytes, lengths, checksums, Z85230 channel selection
and baud therefore remain unproven. Passive capture or an external-bus trace
is required.
