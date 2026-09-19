# DS1230 retention diagnosis after failed U17 application test

Date: 2026-09-19. No write or programming operation was issued during this
diagnostic read.

## Read stability

- Programmer: TL866A, firmware `03.2.86`.
- Exact profile: `DS1230Y(RW)`; `DS1230Y(TEST)` was not used.
- Tool: `minipro 0.7.4`.
- Three new reads: each exactly 32,768 bytes and mutually byte-identical.
- Post-hardware SHA-256:
  `cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19`.
- Ignored raw evidence directory:
  `.local/dyaxis/ds1230-preservation/20260919T214546+0200-retention-diagnosis/`.

## Comparisons

| Reference | SHA-256 | Changed bytes | Changed ranges |
|---|---|---:|---|
| programmed candidate | `cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19` | 0 | none |
| original archive | `2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4` | 6 | `0000–0001`, `7DFC–7DFF` |

Against the original archive, the exact changed bytes are:

| File range | Observed/candidate | Original | Interpretation |
|---|---|---|---|
| `0x0000–0x0001` | `80 FE` | `00 00` | test application payload |
| `0x7DFC–0x7DFF` | `AA 55 FD D7` | `00 00 00 00` | marker/checksum fields |

Separate regions in the observed read:

- Application area `0x0000–0x7DFB`: only `80 FE` is nonzero; it otherwise
  matches the candidate exactly.
- `0x7DFC–0x7DFD`: `AA 55`.
- `0x7DFE–0x7DFF`: `FD D7`.
- Protected/service region `0x7E00–0x7FFF`: unchanged from the candidate and
  original canonical dump; its SHA-256 is
  `79a838798dbba47d83f5ca26385f988d82edcf22eb89e7f60949485970259513`.

No small changed ranges beyond those six bytes exist, and no reads differed
while the device was powered by the programmer.

## Comparison with U17 clear routine `0x03A4`

The exact routine initializes `R6:R7=0x8000`, uses an exclusive endpoint
`0xFDFD`, and performs `MOVX @DPTR,A=0` for CPU addresses `0x8000–0xFDFC`
inclusive. It then explicitly writes zero to `0xFDFE` and `0xFDFF`.

If this routine had cleared the same physical DS1230 mapping after the test,
the candidate's `80 FE` at offsets `0000–0001`, `AA` at `7DFC`, and `FD D7` at
`7DFE–7DFF` would have become zero. `FDFD` and `FE00–FFFF` are intentionally
untouched by this routine. The observed image does not match that clear result:
all candidate bytes remain present. Therefore this test provides no evidence
that `0x03A4` cleared the DS1230.

## Interpretation

The candidate was fully retained; the DS1230 was stable under programmer
power; and the protected FE-page contents survived unchanged. Widespread
battery-retention failure is not supported. A selective U17 clear is also not
supported by the observed bytes. The remaining primary explanation is that
the startup image/marker model or physical CODE/XDATA decode is wrong. The
complete emulator proves that, under the assumed linear XDATA mapping, U17
reaches the checksum path, compares matching low and high bytes, and predicts
**Checksum Good** at `0x02FD`. The physical **Checksum Failed** result
therefore falsifies that mapping hypothesis; the marker branch alone is not an
explanation.

The working boot display is consistent with U17 EPROM code and the preserved
FE-page service/trampoline contents still being available. It does not prove
that the DS1230's application window is mapped linearly, nor that the FE
trampolines are physically fetched from the same memory device. The intact
protected region contradicts complete battery loss but does not by itself
prove the exact chip-select or CODE/XDATA mapping.

No further DS1230 write is authorized until a bus/address-decode measurement
or equivalent hardware evidence resolves that mapping and the dual
`AA55`/checksum use.
