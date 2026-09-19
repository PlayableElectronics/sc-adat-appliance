# U17 FFE1/FFE3 service-window analysis

Only MOVX instructions with a CFG-proven DPTR value are included in
`u17-xdata-xrefs.tsv`. Instructions with unknown or merged DPTR state are
listed in `u17-xdata-unknown.tsv` and are not assigned an address.

`FFE1` is read at `30AA` and `3253`, and written by `3332` and `3348`.
`FFE3` is read by `30C3` and written by `327E`. The conservative interpretation
is a candidate FPGA/peripheral service-register window, possibly decoded or
controlled by PAL logic. It is not proven to be a Macintosh protocol or a
PAL-owned mailbox.
