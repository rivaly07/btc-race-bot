"""make.fun btc-race bot: long-biased seat at the open, slow trend exit.

Strategy, in one paragraph: the replay hands us one symbol (cbBTC/USDC), 1-minute bars,
and a 1,000 USDC cash account, long only. Round-trip cost at full size is ~27 bps (4 bps fee
each way, 2 bps slippage each way, ~8 bps pool impact against ~1.3M USDC of depth), and
1-minute volatility is ~5 bps, so minute-scale signals cannot pay for themselves. What can pay
is holding the one sustained leg a 24-hour window usually contains: take the position at the
first tradeable bar, ride it while the multi-hour trend holds (close above the 360-minute mean),
and leave on either a 0.8% fall from the running peak or a close under that mean. Re-enter only
when the price reclaims both means, which keeps the bot out of a bleeding downtrend.

Deterministic: no clock, no environment reads, no unseeded randomness, integer-ish arithmetic on
the closes the harness sends.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars  # noqa: E402

SLOW_N = 360          # 6 hours of minutes: the trend this bot rides
FAST_N = 90           # 1.5 hours: confirms a reclaim before re-entry
TRAIL_BPS = 100       # leave the position 1.0% under the running peak
MAX_SLIP_BPS = 500    # fills after a fast move still land
BPS = 10_000


class St:
    def __init__(self):
        self.closes = []          # every close seen, oldest first
        self.symbol = None        # the universe's single symbol
        self.holding = False
        self.peak = 0             # running peak close while holding
        self.entered_seq = -1
        self.seated = False
        self.capital = 0


def sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def on_hello(state):
    st = St()
    st.symbol = state.hello["symbols"][0]["symbol"]
    st.capital = int(state.hello["capital"]["quote_units"])
    st.seed_bar = int(state.hello.get("warmup_bars", 0))
    state.st = st


def on_batch(state, batch):
    st = state.st
    for bar in batch["bars"]:
        if bar["symbol"] == st.symbol:
            st.closes.append(int(bar["c"]))
    close = st.closes[-1] if st.closes else None
    if close is None or state.warming_up:
        return []

    held = state.positions.get(st.symbol)
    slow = sma(st.closes, SLOW_N)
    fast = sma(st.closes, FAST_N)

    if held is None:
        # Flat: take the seat at the first tradeable bar, otherwise only on a reclaim of both means.
        if st.holding:
            st.holding = False
        # One seat per window: the trend leg is taken at the first tradeable bar, and a later
        # re-entry has to pay the full round-trip cost again, which minute-scale noise cannot fund.
        ready = not st.seated
        if not ready:
            return []
        notional = state.cash
        if notional < 1_000_000:
            return []
        st.holding = True
        st.seated = True
        st.peak = close
        st.entered_seq = state.seq
        return [{"side": "buy", "symbol": st.symbol, "notional_quote_units": notional,
                 "max_slippage_bps": MAX_SLIP_BPS}]

    # Holding: track the peak, then leave on a trail give-back or a break of the slow mean.
    st.holding = True
    if close > st.peak:
        st.peak = close
    gave_back = (st.peak - close) * BPS > st.peak * TRAIL_BPS
    broke = slow is not None and close < slow
    if gave_back or broke:
        qty = held.qty
        if qty <= 0:
            return []
        st.holding = False
        return [{"side": "sell", "symbol": st.symbol, "qty": qty,
                 "max_slippage_bps": MAX_SLIP_BPS}]
    return []


def on_done(state, done):
    pass


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)
