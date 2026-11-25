#!/usr/bin/env bash
# Controller-side entry point. Run as labadmin, not sudo.
# Examples:
# bash tools/rollout.sh deploy localhost/opsportal:manual2 ~/opsportal-manual2.tar manual2
# bash tools/rollout.sh rollback
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
mkdir -p evidence

# Prevent two runs from this checkout overwriting rollback references.
exec 9>"$project_dir/.rollout.lock"
flock -n 9 || { echo 'Another rollout is running from this checkout.' >&2; exit 1; }

mode="${1:-}"
if [[ "$mode" != deploy && "$mode" != rollback ]]; then
  echo 'Usage: bash tools/rollout.sh deploy IMAGE ARCHIVE VERSION | rollback' >&2
  exit 2
fi
if [[ "$mode" == deploy && $# != 4 ]] || [[ "$mode" == rollback && $# != 1 ]]; then
  echo 'Wrong argument count.' >&2
  exit 2
fi

run_dir="$(mktemp -d "$project_dir/evidence/rollout.XXXXXX")"
echo "Evidence directory: $run_dir"

# Both playbooks must parse before any application configuration is changed.
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/rollback.yml --syntax-check

# Record HTTPS responses throughout deployment/recovery; keep failures honestly.
python3 tools/goal6-probe.py "$run_dir/requests.csv" &
probe_pid=$!
finish() {
  kill -TERM "$probe_pid" 2>/dev/null || true
  wait "$probe_pid" 2>/dev/null || true
  python3 - "$run_dir/requests.csv" <<'PY'
import csv, sys
with open(sys.argv[1], newline='') as f:
    rows = list(csv.DictReader(f))
bad = sum(r['status'] != '200' for r in rows)
print('HTTPS samples:', len(rows), '| Failed:', bad)
if rows:
    print('Failure rate: %.2f%%' % (100 * bad / len(rows)))
print('Request evidence:', sys.argv[1])
PY
}
trap finish EXIT

if [[ "$mode" == rollback ]]; then
  ansible-playbook -i ansible/inventory.ini ansible/rollback.yml \
    2>&1 | tee "$run_dir/rollback.log"
  exit 0
fi

archive="$(realpath -- "$3")"
python3 - "$2" "$archive" "$4" "$run_dir/preflight.ok" "$run_dir/inputs.json" <<'PY'
import json, os, sys
values = dict(zip(('image_ref', 'image_archive', 'release_version', 'transaction_marker'), sys.argv[1:5]))
with open(sys.argv[5], 'w') as f:
    json.dump(values, f)
os.chmod(sys.argv[5], 0o600)
PY

if ansible-playbook -i ansible/inventory.ini ansible/deploy.yml \
    --extra-vars "@$run_dir/inputs.json" 2>&1 | tee "$run_dir/deploy.log"; then
  echo 'Deployment passed on both application servers.'
else
  deploy_rc=$?
  if [[ -f "$run_dir/preflight.ok" ]]; then
    echo 'Deployment failed after preflight. Restoring BOTH transaction-start releases.'
    if ansible-playbook -i ansible/inventory.ini ansible/rollback.yml \
        2>&1 | tee "$run_dir/rollback.log"; then
      echo 'Both previous releases verified. The deployment is still reported as failed.'
    else
      echo 'Rollback did not complete. Inspect the saved logs before further changes.' >&2
    fi
  else
    echo 'Preflight failed; no application image was switched. Rollback was not run.' >&2
  fi
  exit "$deploy_rc"
fi
