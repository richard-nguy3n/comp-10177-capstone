# Goal 6: manual Ansible rolling deployment and rollback

This batch implements the manual deployment prerequisite of Phase 10. It does
not register a GitHub Actions runner or claim a successful live deployment.

## Current lab design

- MGMT01: one NIC, 192.168.30.10; run these tools as labadmin.
- APP01/APP02: 192.168.20.21/.22; rootful Podman, opsportal Quadlet.
- Inventory: labdeploy with MGMT01's dedicated capstone_ed25519 key.
- Portal: https://portal.opsdemo.test using system-trusted lab CA.
- Database/schema/environment files are preserved.

Keep FW01, DC01, MGMT01 and both app servers running. Preserve a known-good
recovery point before the first rollout. Do not run concurrent deployments.

## Transfer

Download the archive on Windows and use scp to send it to labadmin@192.168.30.10.
On MGMT01, inspect the archive with tar -tzf, then extract into ~/capstone using
tar --keep-old-files -xzf. This option refuses to replace an existing file.
If extraction reports a conflict, inspect it before running a deployment.

## Run

From ~/capstone, inspect git status and syntax-check both playbooks, then:

    bash tools/rollout.sh deploy localhost/opsportal:manual2 ~/opsportal-manual2.tar manual2

Expected: APP01 updates before APP02; each local health reports manual2 and its
running image ID matches the built image. Trusted HTTPS stays observable through
the automatic probe. Brief failed requests may occur; use the actual CSV.

After a successful deployment, demonstrate returning to cp1:

    bash tools/rollout.sh rollback

Expected: both nodes return to the exact transaction-start image ID and embedded
version, local /health succeeds, and the trusted HTTPS endpoint returns 200.

## Design notes

- The proposal requires rolling deployment and rollback. This implementation
  changes only Image= in the existing Quadlet rather than replacing it with a
  generic template. Rollback restores its complete saved content. This preserves
  the actual working service options and avoids extra-vars/template precedence.
- Preflight verifies both starting image identities/versions and the controller
  image/archive. It snapshots previous.container and previous-image on both apps
  and writes a fresh controller marker only after the entire preflight succeeds.
- Any deployment failure after that marker triggers whole-transaction rollback.
  The rejected node is also restored immediately by its rescue block. This
  covers failures on the second node after the first has already updated.
- Successful rollback does not turn a rejected deployment into a successful run.
- Rootless controller images are exported and loaded into rootful app storage.
- Keep previous images; do not retag/prune them. Do not rerun deploy as a recovery
  action, because that starts a new transaction and replaces rollback snapshots.
- APP_VERSION must not be overridden in portal.env. A mismatch makes verification
  fail and triggers recovery. An unreachable node may prevent automatic recovery.
- The eight-second backend wait follows the manual's reference health settings;
  verify HAProxy backends are UP before acceptance. The HTTPS check alone does not
  prove that both backends are healthy.
- The lock serializes runs in this checkout. GitHub runner concurrency and its
  own key/inventory paths still need configuration in the next batch.

## Evidence and limitations

Each invocation creates evidence/rollout.XXXXXX with playbook logs and an HTTPS
CSV (UTC, HTTP status, node, version, latency, error). Requests are sequential,
with a one-second pause and a five-second request timeout. Sampling does not
prove zero sub-second outage or exact HAProxy failover timing. A Ctrl+C can
interrupt recovery; inspect state before restarting any transaction.

The existing pytest tests and temporary-container health validation belong to
the remaining CI pipeline work. No live lab tests have been run by this package's
author. Verify the real results before recording success.

Never commit portal.env, private keys, PATs or runner-registration tokens. Keep
the existing baseline, inventory and bootstrap playbook under version control.
