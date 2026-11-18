# BTC Dip-Buy Bot — make.fun "Race a BTC trading bot live for 24 hours"

A Python 3.13 (stdlib-only) trading bot for the make.fun bounty
[btc-race-24h-20261118-1444](https://make.fun/bounty/btc-race-24h-20261118-1444).
It trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute on-chain bars,
starting from $1,000 of paper money. Simulation only — no real money is traded.

## Strategy

Bitcoin on a 1-minute chart mostly chops sideways, so lagging trend-following
entries whipsaw: every round trip costs ~26 bps in fees, slippage and pool
impact. This bot waits flat in cash and only buys a **deep pullback** — the
close at least **1.5% below the highest close of the last 180 minutes**, or at
least **2.0% below the highest close of the last 60 minutes** — then sells the
bounce at a fixed **+1.0% take-profit** or a **−0.8% stop**, with a 480-bar
maximum hold. It never opens a position in the last 180 bars of the window,
and it halts trading if equity ever falls 5% below its running peak. Long-only,
at most one full-size position, fully deterministic (a pure function of the
bars; no clock, no network, no randomness).

Local dev-window result (via the kit's `grade-local`): **net PnL ≈ +$24.21**,
6 trades, max drawdown ≈ 0.63%.

## How to run

```sh
# Grade locally against the frozen dev window (needs the kit):
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . --driver process
```

Or run the bot directly against a replay harness speaking
`agent-fun/bars-replay/v1` on stdin/stdout:

```sh
python3 main.py
```

## Files

- `main.py` — the bot (entrypoint)
- `vendor/makefun_bars.py` — byte-for-byte copy of the kit's Python SDK shim
- `README.md` — this file
- `LICENSE` — MIT

[![make.fun bounty](https://make.fun/bounty/btc-race-24h-20261118-1444/badge.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![make.fun](https://make.fun/badge.svg)](https://make.fun)
[![btc-race-24h-20261118-1444](https://make.fun/bounty/btc-race-24h-20261118-1444/shield.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
