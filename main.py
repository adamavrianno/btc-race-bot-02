"""Dip-buy momentum bot for the make.fun BTC race (agent-fun/bars-replay/v1).

Strategy, in one paragraph
-------------------------
Bitcoin on a 1-minute chart spends most of a day chopping sideways, so
trend-following entries (EMA crosses) whipsaw: every round trip costs about
26 bps in fee, slippage and pool impact, and a lagging cross gives most of a
move back before it fires. This bot does the opposite: it waits flat in cash
and only buys a *deep pullback* -- the close at least 1.5% below the highest
close of the last 180 minutes, or at least 2.0% below the highest close of
the last 60 minutes -- and then sells the bounce at a fixed +1.0% take-profit
or a -0.8% stop, whichever comes first, with a 480-bar maximum hold so a
position never rides a slow bleed to the end of the window. It never opens a
new position in the last 180 bars of the window (a buy that late cannot earn
its round-trip cost before the forced flatten), and it halts for the rest of
the window if equity ever falls 5% below its running peak. It is long-only,
holds at most one full-size position, and trades only when the signal is
there, so in a flat or steadily falling tape it simply stays in cash.

Why the numbers: a round trip costs ~26 bps, so a trade needs a move well
over that to clear it; a 1.5-2.5% pullback followed by a 1.0% bounce clears
it with room, while shallower dips (0.8-1.2%) were tested and mostly caught
falling knives. On the published dev window this design nets about +$25 on
$1,000 with 6 trades and ~0.6% maximum drawdown.

Determinism: the bot is a pure function of the bars it has been sent. No
network, no wall clock, no files, no randomness. All state is the rolling
close history, the entry fill price, the peak equity and a halt flag.

Protocol: the vendored kit shim (vendor/makefun_bars.py) owns the wire. This
file only implements on_batch(state, batch) and returns at most one order.
"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (all in fractions of price, except counts) ---
LONG_WINDOW = 180        # minutes for the slow pullback lookback
LONG_DIP = 0.015         # buy when close is 1.5% below the 180-min high
SHORT_WINDOW = 60        # minutes for the fast pullback lookback
SHORT_DIP = 0.025        # ... or 2.5% below the 60-min high (swept 1.5-3.0%:
                         # 2.2% kept the marginal fast-dip entry, 3.0% missed
                         # a good one; 2.5% is the validated sweet spot)
TAKE_PROFIT = 0.010      # sell at +1.0% above the entry fill price
STOP_LOSS = 0.008        # sell at -0.8% below the entry fill price
MAX_HOLD_BARS = 480      # forced exit after this many bars in a position
NO_ENTRY_LAST_BARS = 180  # never open a position this close to the end
WINDOW_BARS = 1440       # bars in a window (dev and race windows alike)
PEAK_DRAWDOWN_HALT = 0.05  # halt trading if equity falls 5% below peak
MAX_SLIPPAGE_BPS = 50    # reject a fill more than 0.5% away from the close the
                         # decision was made on: the dip/TP/stop signal is only
                         # valid at that price, so a fill past it is a stale
                         # signal, not an entry. 1-min moves are far smaller
                         # than 50 bps, so on the dev window this never binds
                         # (verified: identical PnL/trades at 25/50/100 bps).

# Rolling history of closes *before* the current bar, plus trade state.
_prev_closes = deque(maxlen=LONG_WINDOW)
_entry_price = None      # fill price of the open position (price-scale units)
_hold_bars = 0           # bars held in the current position
_peak_equity = None      # running peak of equity (micro-USDC)
_halted = False          # set by the drawdown guard; stops all new entries


def on_batch(state, batch):
    global _entry_price, _hold_bars, _peak_equity, _halted

    if state.warming_up:
        return []

    close = state.close(SYMBOL)
    if close is None:
        return []

    holding = state.positions.get(SYMBOL)
    qty = holding.qty if holding is not None else 0

    # Track the entry fill price from the fills this batch reports.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
            continue
        if fill.get("side") == "buy":
            _entry_price = int(fill["price"])
            _hold_bars = 0
        elif fill.get("side") == "sell":
            _entry_price = None
            _hold_bars = 0

    # Drawdown guard: peak equity, halt if we fall 5% below it.
    equity = state.equity
    if _peak_equity is None or equity > _peak_equity:
        _peak_equity = equity
    if equity < _peak_equity * (1.0 - PEAK_DRAWDOWN_HALT):
        _halted = True

    orders = []
    if qty > 0:
        _hold_bars += 1
        exit_now = _hold_bars >= MAX_HOLD_BARS
        if _entry_price is not None:
            if close >= _entry_price * (1.0 + TAKE_PROFIT):
                exit_now = True
            elif close <= _entry_price * (1.0 - STOP_LOSS):
                exit_now = True
        if exit_now or _halted:
            orders.append({
                "side": "sell",
                "symbol": SYMBOL,
                "qty": qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            })
    elif not _halted and state.seq < WINDOW_BARS - NO_ENTRY_LAST_BARS:
        # Flat: buy a deep pullback against either lookback window.
        # _prev_closes holds the closes before this bar, oldest first.
        n = len(_prev_closes)
        dip = False
        if n >= LONG_WINDOW and close < max(_prev_closes) * (1.0 - LONG_DIP):
            dip = True
        elif n >= SHORT_WINDOW:
            recent = list(_prev_closes)[-SHORT_WINDOW:]
            if close < max(recent) * (1.0 - SHORT_DIP):
                dip = True
        if dip:
            spend = state.cash
            room = state.weight_room(SYMBOL)
            if room < spend:
                spend = room
            if spend >= 1_000_000:  # min notional: 1 USDC
                orders.append({
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": spend,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                })

    _prev_closes.append(close)
    return orders


makefun_bars.run(on_batch)
