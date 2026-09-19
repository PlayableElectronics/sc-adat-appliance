# U17 standalone capabilities

Confirmed U17-local behavior includes reset/startup sequencing, external RAM
clear/checksum/signature validation, boot/checksum/master-reset message
selection through FE06 services, peripheral/service initialization, timeout
handling, external-RAM transfer and an external-code launch at `0x8000`.

Standalone fader, LED and display activity is confirmed at the console level,
but this U17 ROM alone does not contain a statically proven complete fader/LED
driver loop. The XC3030 probably implements scanning/interface logic and the
PAL likely supplies glue/decode/control logic; exact assignments remain partly
inferential.
