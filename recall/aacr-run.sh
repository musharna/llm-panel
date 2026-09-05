#!/bin/bash
# Clean 3-judge AACR-Bench run.
#
# SNAPSHOTS THE BINARIES FIRST. The pilot batch was contaminated because I edited
# llm-panel while it was running: the bridge process held its own code from start, but
# llm-panel is re-invoked per instance, so half the batch used a different binary than the
# other half. `git rev-parse HEAD` does not identify what actually ran. This copies the
# three files into the run directory, records their md5s, and executes THOSE -- so an edit
# during the run cannot reach it.
# -e and pipefail: with -u alone a failed POSITIVE leg ran straight into the NEGATIVE one
# and printed ALL PANELS DONE, indistinguishable from a run that worked.
set -euo pipefail
R="$1"; TIMEOUT="${2:-900}"
S="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$R/bin/recall"
cp "$S/llm-panel" "$S/claimlib.py" "$R/bin/"
cp "$S/recall/aacr-upstream" "$R/bin/recall/"
chmod +x "$R/bin/llm-panel" "$R/bin/recall/aacr-upstream"
{ echo "# binaries actually executed by this run"; date '+# started %F %T %Z'
  echo "# timeout=${TIMEOUT}s judges=codex,big-pickle,nemotron effort=high"
  md5sum "$R/bin/llm-panel" "$R/bin/claimlib.py" "$R/bin/recall/aacr-upstream"
  echo "# source git HEAD: $(git -C "$S" rev-parse HEAD)"
  echo "# source tree clean: $(git -C "$S" status --porcelain | wc -l) modified files"
} > "$R/BINARIES.txt"
cat "$R/BINARIES.txt"
export PATH="$R/bin:$PATH"

echo; echo "=== POSITIVE (20 instances, seed 42) ==="
"$R/bin/recall/aacr-upstream" run \
  --instances "$S/recall/benchmarks/upstream/pos-seed42-n20.jsonl" \
  --out "$R/pos" --judges codex,big-pickle,nemotron --effort high --timeout "$TIMEOUT"
echo; echo "=== NEGATIVE (10 instances, seed 42) ==="
"$R/bin/recall/aacr-upstream" run \
  --instances "$S/recall/benchmarks/upstream/neg-seed42-n10.jsonl" \
  --out "$R/neg" --judges codex,big-pickle,nemotron --effort high --timeout "$TIMEOUT"
echo; date '+# finished %F %T %Z'; echo "=== ALL PANELS DONE ==="
