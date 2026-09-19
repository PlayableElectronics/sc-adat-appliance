#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"

smoke=$(./dyaxis/analysis/run_u17_ucsim.sh --smoke)
SMOKE_JSON="$smoke" python3 - <<'PY'
import json, os
p = json.loads(os.environ["SMOKE_JSON"])
assert p["stop_event"] is True, p
assert p["actual_stop_pc"] == "0x0005", p
assert p["actual_state_pc"] == "0x0005", p
assert p["actual_accumulator"] == "0x42", p
PY

reset=$(./dyaxis/analysis/run_u17_ucsim.sh --experiment B)
RESET_JSON="$reset" python3 - <<'PY'
import json, os
p = json.loads(os.environ["RESET_JSON"])["experiments"][0]
assert p["stop_reason"] == "explicit Stop-at event 0x2F6F", p
assert p["final_path"] == "reset-entry", p
assert p["uCsim_state_pc"] == "0x2F6F", p
assert p["breakpoint_fetches"] == ["0x2F6F"], p
assert p["execution_status"] == "terminal breakpoint observed", p
assert p["static_path_projection"] == "Checksum Good", p
PY

echo "uCsim integration: synthetic smoke and U17 reset-entry passed"
