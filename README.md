# BritPool independent verification

Several times a day, GitHub's own servers check the [BritPool](https://britpool.com) Bitcoin Cash
solo mining pool and publish the result here. The pool operator can't edit GitHub's run logs,
and every check ever run stays in this repository's history.

**Latest result:** [`results/latest.json`](results/latest.json)
**Every result so far:** [`results/history.jsonl`](results/history.jsonl)
**Full logs of each run:** the [Actions tab](../../actions)

## What is checked

Each run connects to `bch.britpool.com:3334` over TLS, checking the pool's certificate, and:

1. **Payout to the miner:** logs in as a miner using a **freshly generated random BCH address**
   and checks that the block reward in the work it's given is paid **100% to that address**, in a
   single output (so a **0% pool fee**). Because the address is new every time, the pool can't
   recognise a "test" address and treat it differently. Only the work is inspected; no shares are
   submitted and no funds are involved.
2. **Typo protection:** logs in with a one-character typo of that address and checks the pool
   **refuses** it, so a mistyped address can't silently mine to nowhere.
3. **Unique work:** opens five connections and checks each receives different work (extranonce1),
   so no miner's effort duplicates another's.

If any check fails, the run is marked failed and the repository owner is notified by GitHub.

## What runs

- [`.github/workflows/verify.yml`](.github/workflows/verify.yml): the schedule, and exactly what runs.
- [`scripts/run_checks.py`](scripts/run_checks.py): runs the three checks and writes the results.
- The checks themselves use `verify_pool.py` from
  [IanWesterGitHub/stratum-speed-test](https://github.com/IanWesterGitHub/stratum-speed-test), a fork of
  [mweinberg/stratum-speed-test](https://github.com/mweinberg/stratum-speed-test) with Bitcoin Cash
  support. It is fetched at the **exact commit** named in the workflow file, so you can see which
  code ran, compare it with the original, and run the same checks yourself.

## Check it yourself

```bash
git clone https://github.com/IanWesterGitHub/stratum-speed-test.git
cd stratum-speed-test
python3 verify_pool.py bch.britpool.com 3334 YOUR-BCH-ADDRESS --tls
```

## Limits

This checks the work the pool hands out at the moment of each run. The workflow is scheduled
hourly, but GitHub runs free scheduled jobs on a best-effort basis and often skips slots, so in
practice checks run several times a day, typically every few hours.
