FROM debian:13-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 sdcc-ucsim=4.5.0+dfsg-1 \
    && rm -rf /var/lib/apt/lists/* \
    && test "$(ucsim_51 -V 2>&1 | head -1)" = "uCsim 0.8.15, Copyright (C) 1997 Daniel Drotos."

ENTRYPOINT ["python3", "/work/dyaxis/analysis/u17_ucsim_runner.py", "--ucsim", "/usr/bin/ucsim_51"]
