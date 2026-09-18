# Prioritized hardware observations

These are the smallest observations that static ROM analysis cannot resolve.
No transmission is requested.

1. **Best next experiment: passive event capture.** The supplied close-up now
   identifies an `AM26LS32PC` receiver at U4 and an `SN75174N` driver at U13.
   With power off, continuity-map their four receiver/driver channels to the
   rear `(RS422) SERIAL 1/2` connector pins and identify the signal reference.
   Then connect a high-impedance differential RS-422 receiver to one confirmed
   pair and reference ground. Capture power-up followed by exactly
   one button press. Repeat once for one encoder/wheel movement. Capture both
   directions only with receive-only inputs. This directly tests whether the
   U3 `FD/FE` handling and `0x80..F0` event family appear on a rear port.
2. Photograph the main CPU board square-on so the U3/U17 socket references,
   J1/J2 traces, `12.000 MHz` marking, RS-422 transceivers and Z85230 full
   marking are readable.
3. Photograph the FPGA cluster square-on with both Studer ROM references and
   the XC3030 configuration pins/ROM traces visible. Do not remove the nearby
   8-pin device; its marking is currently insufficient for identification.
4. During the same passive capture, record which displayed text changes and
   which LEDs/faders react. That correlates U17 external display calls, U3
   output multiplexing, and U7 local-control activity without guessing a
   packet format.

Do not attach TTL UART hardware directly to an unknown board net, and do not
transmit until the differential pair, direction, reference ground and safe
receiver interface are established.
