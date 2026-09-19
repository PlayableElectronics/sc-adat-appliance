#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PIN=a32d0adc80cfbf203745318900ced5ea94303b15
VENV=${U17_VENV:-"$ROOT/.local/disasm51-venv"}

mkdir -p "$(dirname "$VENV")"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
installed_commit=$(
  "$VENV/bin/python" - <<'PY'
import importlib.metadata as metadata
import json
import subprocess
from urllib.parse import urlparse
from pathlib import Path
try:
    distribution = metadata.distribution("disasm51")
    info = json.loads((Path(distribution._path) / "direct_url.json").read_text())
    commit = info.get("vcs_info", {}).get("commit_id", "")
    if not commit and info.get("url", "").startswith("file:"):
        source = Path(urlparse(info["url"]).path)
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    print(commit)
except Exception:
    print("")
PY
)
if [ "$installed_commit" != "$PIN" ]; then
  "$VENV/bin/python" -m pip install --no-deps \
    "git+https://github.com/OlekMazur/disasm51@$PIN" || {
      echo "unable to install disasm51 at required commit $PIN" >&2
      exit 2
    }
  installed_commit=$(
    "$VENV/bin/python" - <<'PY'
import importlib.metadata as metadata
import json
from pathlib import Path
distribution = metadata.distribution("disasm51")
print(json.loads((Path(distribution._path) / "direct_url.json").read_text())
      .get("vcs_info", {}).get("commit_id", ""))
PY
  )
fi
if [ "$installed_commit" != "$PIN" ]; then
  echo "disasm51 is not installed at required commit $PIN" >&2
  exit 2
fi
DISASM51_BIN="$VENV/bin/disasm51" \
  "$ROOT/dyaxis/analysis/run_u17_analysis.sh"
PYTHONPATH="$ROOT" "$VENV/bin/python" -m unittest dyaxis.analysis.test_deep_u17_analysis
