#!/usr/bin/env python3
"""
Run the BritPool verification checks and record the results.

Uses verify_pool.py from IanWesterGitHub/stratum-speed-test (checked out at a
pinned commit into ./verifier by the workflow) and runs three checks against
the live pool:

  1. payout       - a freshly generated random BCH address is paid 100% of the
                    block reward, in a single output (so 0% pool fee)
  2. typo_refused - a one-character typo of that address is refused at login
                    (so a mistyped address can't silently mine to nowhere)
  3. unique_work  - five connections each receive different work (extranonce1)

Writes results/latest.json and appends one line to results/history.jsonl.
Exits non-zero if any check fails, so GitHub marks the run as failed and
emails the repository owner.

Settings (environment variables): POOL_HOST, POOL_PORT, POOL_TLS ("1"/"0").
"""

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIER_DIR = os.environ.get("VERIFIER_DIR", os.path.join(ROOT, "verifier"))
VERIFIER = os.path.join(VERIFIER_DIR, "verify_pool.py")
RESULTS = os.path.join(ROOT, "results")

POOL_HOST = os.environ.get("POOL_HOST", "bch.britpool.com")
POOL_PORT = os.environ.get("POOL_PORT", "3334")
POOL_TLS = os.environ.get("POOL_TLS", "1") == "1"

sys.path.insert(0, VERIFIER_DIR)
import verify_pool  # noqa: E402  (only used to generate the random test address)


def run_verifier(*args):
    """Run verify_pool.py with --json; return (exit_code, report_dict).
    The human-readable output (stderr) is passed through to the Actions log."""
    cmd = [sys.executable, VERIFIER, POOL_HOST, POOL_PORT, *args, "--json",
           "--timeout", "30", "--retries", "1"]
    if POOL_TLS:
        cmd.append("--tls")
    print(f"\n$ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    sys.stdout.write(proc.stderr)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"result": "error", "raw_output": proc.stdout[-2000:]}
    return proc.returncode, report


def heading(text):
    print("\n" + "=" * 78, flush=True)
    print(text, flush=True)
    print("=" * 78, flush=True)


def typo_of(address):
    """Change the last character, which breaks the CashAddr checksum."""
    last = address[-1]
    return address[:-1] + ("q" if last != "q" else "p")


def main():
    address = verify_pool.generate_random_bch_address()

    # 1. Payout to a never-before-seen address
    heading("CHECK 1 of 3: the block reward must go 100% to a brand-new random address\n"
            "(expected result: VERIFICATION PASSED)")
    _, payout = run_verifier(address, "--coin", "bch")
    outputs = payout.get("outputs") or []
    paying = [o for o in outputs if o.get("satoshis", 0) > 0]
    payout_ok = (payout.get("result") == "passed"
                 and len(paying) == 1
                 and paying[0].get("address") == address
                 and paying[0].get("percent") == 100.0)

    # 2. A mistyped address must be refused at login
    heading("CHECK 2 of 3: a mistyped address must be REFUSED by the pool\n"
            "(expected result: 'Authorization failed' - a refusal here means the check PASSED)")
    _, typo = run_verifier(address, "--coin", "bch", "--username", typo_of(address))
    typo_ok = typo.get("result") == "auth_refused"

    # 3. Each connection gets unique work
    heading("CHECK 3 of 3: every connection must receive unique work\n"
            "(expected result: All extranonce1 values are unique)")
    _, unique = run_verifier("--coin", "bch", "--test-extranonce")
    unique_ok = unique.get("result") == "passed" and unique.get("all_unique") is True

    passed = payout_ok and typo_ok and unique_ok
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")

    latest = {
        "passed": passed,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pool": f"{POOL_HOST}:{POOL_PORT}",
        "tls": POOL_TLS,
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else None,
        "verifier": {
            "repository": os.environ.get("VERIFIER_REPO", "IanWesterGitHub/stratum-speed-test"),
            "commit": os.environ.get("VERIFIER_COMMIT", "unknown"),
        },
        "block_height": payout.get("block_height"),
        "pool_signature": payout.get("pool_signature"),
        "checks": {
            "payout_to_miner": {
                "passed": payout_ok,
                "test_address": address,
                "paying_outputs": len(paying),
                "miner_percent": paying[0].get("percent") if len(paying) == 1 else None,
                "total_satoshis": payout.get("total_satoshis"),
                "result": payout.get("result"),
            },
            "typo_refused": {"passed": typo_ok, "result": typo.get("result")},
            "unique_work": {"passed": unique_ok, "result": unique.get("result")},
        },
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "latest.json"), "w") as f:
        json.dump(latest, f, indent=2)
        f.write("\n")
    with open(os.path.join(RESULTS, "history.jsonl"), "a") as f:
        f.write(json.dumps({
            "checked_at": latest["checked_at"],
            "passed": passed,
            "block_height": latest["block_height"],
            "payout": payout_ok, "typo_refused": typo_ok, "unique_work": unique_ok,
            "run_url": latest["run_url"],
        }) + "\n")

    mark = lambda ok: "PASS" if ok else "FAIL"
    heading(f"OVERALL: {mark(passed)}\n"
            f"  Check 1 - 100% of the reward to the miner:  {mark(payout_ok)}\n"
            f"  Check 2 - mistyped address refused:         {mark(typo_ok)}\n"
            f"  Check 3 - unique work for every miner:      {mark(unique_ok)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
