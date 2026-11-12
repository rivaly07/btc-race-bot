"""make.fun btc-race bot: buy the flush, sell the bounce, protect breakeven.

Strategy, in one paragraph: the replay hands us one symbol (cbBTC/USDC), 1-minute bars, and a
1,000 USDC cash account, long only. A round trip at full size costs ~26 bps (4 bps fee each way,
2 bps slippage each way, ~7 bps pool impact on ~1.3M USDC of depth) while 1-minute volatility is
~5 bps, so a bot cannot scalp noise: every entry has to be a real dislocation that the market
repairs. The one structure that pays is a fast flush and its snap-back. When the close sits more
than 0.60% under the highest close of the last 15 minutes -- a move the minute-scale noise band
cannot produce -- the bot buys the flush and sells on a 0.90% bounce. A 0.30% stop cuts a flush
that keeps going; once the trade has shown 0.30% of profit the stop moves to breakeven, so a
bounce that stalls costs nothing. That combination is what makes the bot regime-agnostic: in an
uptrend the flush is a dip that recovers, in a downtrend it is a panic wick that snaps back, and
in either case the trade is paid by the repair, not by the direction of the window.

Deterministic: no clock, no environment reads, no randomness; integer bps arithmetic on the
closes the harness sends.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars  # noqa: E402

LOOKBACK = 15         # minutes of high-water mark the flush is measured against
DROP_BPS = 60         # 0.60% under that high-water mark: a repair-worthy dislocation
TP_BPS = 90           # 0.90% bounce: the repair this bot is paid for
SL_BPS = 30           # 0.30% against us: the flush was real, leave
BE_ARM_BPS = 30       # once 0.30% in profit, the stop moves to breakeven
MAX_RT = 12           # round trips per window: each one must pay its own 26 bps
COOLDOWN = 60         # bars to wait after an exit before hunting again
MAX_SLIP_BPS = 500    # fills after a fast move still land
BPS = 10_000


class St:
    def __init__(self):
        self.closes = []          # every close seen, oldest first
        self.symbol = None        # the universe's single symbol
        self.holding = False
        self.entry = 0            # close at which the current trade was opened
        self.peak = 0             # running peak close while holding
        self.armed = False        # breakeven stop unlocked
        self.rts = 0              # round trips used in this window
        self.last_exit = -10 ** 9
        self.i = 0


def on_hello(state):
    st = St()
    st.symbol = state.hello["symbols"][0]["symbol"]
    state.st = st


def on_batch(state, batch):
    st = state.st
    for bar in batch["bars"]:
        if bar["symbol"] == st.symbol:
            st.closes.append(int(bar["c"]))
            st.i += 1
    if state.warming_up or not st.closes:
        return []
    close = st.closes[-1]
    held = state.positions.get(st.symbol)

    if held is not None:
        if not st.holding:
            st.holding = True
            st.entry = close
            st.peak = close
            st.armed = False
        if close > st.peak:
            st.peak = close
        chg_bps = (close - st.entry) * BPS // st.entry
        if not st.armed and (st.peak - st.entry) * BPS // st.entry >= BE_ARM_BPS:
            st.armed = True
        floor_bps = 0 if st.armed else -SL_BPS
        if chg_bps >= TP_BPS or chg_bps <= floor_bps:
            qty = held.qty
            if qty <= 0:
                return []
            st.holding = False
            st.armed = False
            st.rts += 1
            st.last_exit = st.i
            return [{"side": "sell", "symbol": st.symbol, "qty": qty,
                     "max_slippage_bps": MAX_SLIP_BPS}]
        return []

    st.holding = False
    if st.rts >= MAX_RT or st.i - st.last_exit < COOLDOWN:
        return []
    if len(st.closes) < LOOKBACK + 1 or state.cash < 1_000_000:
        return []
    high = max(st.closes[-LOOKBACK - 1:-1])
    if (high - close) * BPS < high * DROP_BPS:
        return []
    st.entry = close
    st.peak = close
    st.armed = False
    st.holding = True
    return [{"side": "buy", "symbol": st.symbol, "notional_quote_units": state.cash,
             "max_slippage_bps": MAX_SLIP_BPS}]


def on_done(state, done):
    pass


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)
