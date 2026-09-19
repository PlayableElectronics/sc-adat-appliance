# U17 FFE1/FFE3 service-window analysis

`FFE1` is read at `30AA` and `3253`, and written by `3332` and `3348`.
`FFE3` is read by `30C3` and written by `327E`. The complete literal xref list
is `u17-xdata-xrefs.tsv`.

The strongest conservative interpretation is a candidate FPGA/peripheral
service-register window, possibly decoded or controlled by PAL logic. The ROM
does not prove that the PAL owns it, that it is a mailbox to a processor, or
that it is the Macintosh protocol.

The service values `01`, `02`, `06` and `FF` have state-dependent effects in
the generated state table. Values `06` and `FF` enter the external-RAM transfer
path and are not safe candidates for active control testing.
