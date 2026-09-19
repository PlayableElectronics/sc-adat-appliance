; First non-peripheral U17 external application validation image.
; Linked CPU CODE address: 8000h.
; Exact payload bytes: 80 FE.
; SJMP $: remain at the entry point after U17 executes LCALL 8000h.
;
; This source intentionally performs no display, serial, fader, LED, timer,
; or other peripheral operation.

        ORG 8000h
        SJMP $
