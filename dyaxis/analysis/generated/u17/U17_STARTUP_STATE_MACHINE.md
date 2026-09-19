# U17 startup state machine

```text
0000 -> 2F6F: clear internal RAM; clear XDATA 0000..7FFF and FE00..FEFF
2FD2: apply ROM table 2211 initialization; enter 01E0
01E0: disable interrupts; external services; FFF1/FFF0 status test
      FEEE/FEEF setup; Timer-2/capture setup; enable EA
      FE06 boot/checksum/master-reset messages; validate RAM/signature
30A7: initialize candidate peripheral/service window through 3348
30AA: wait on FFE1.0; consume FFE3; dispatch state A8
3253: timeout/status handling; return to 30AA
328A: disable services and launch external code at 8000, or reset path
```

The exact host-wait interpretation remains unresolved. `FFE1/FFE3` is a
candidate FPGA/peripheral service-register window, possibly decoded or
controlled by PAL logic; it is not proven to be Macintosh wire traffic.
