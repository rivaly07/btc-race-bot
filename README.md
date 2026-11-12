# btc-race bot

make.fun `btc-race-24h` entry. One symbol (cbBTC/USDC), 1-minute bars, 1,000 USDC of paper
capital, long only, about 1.3M USDC of pool depth.

## What it does

The replay costs a full-size round trip about 26 bp: 4 bp of fee each way, 2 bp of slippage each
way, and roughly 7 bp of constant-product impact on 1,000 USDC. One-minute volatility on this
pair is about 5 bp, so no minute-scale signal can fund a trade by itself. What can fund one is a
dislocation big enough that the market repairs it:

- **enter**: when the close sits more than **0.60%** under the highest close of the last **15**
  minutes — a move the minute-scale noise band cannot produce — buy the flush with all of
  `state.cash`
- **take profit**: sell on a **0.90%** bounce; that repair is the trade
- **stop**: **0.30%** against us, the flush was real
- **breakeven**: once the trade has shown **0.30%** of profit the stop moves to entry, so a bounce
  that stalls costs nothing
- **limits**: at most 12 round trips per window, 60 bars of cooldown after each exit

That combination is regime-agnostic on purpose. In an uptrend a flush is a dip that recovers; in a
downtrend it is a panic wick that snaps back; in both cases the bot is paid by the repair, not by
the direction of the window. The previous revision of this bot was a long seat that only earned
when the window rose.

`max_slippage_bps` is 500 so a stop still fills after a fast move.

## Dev-window result (kit `btc-race-24h-20261112-1439`, `--driver docker`)

```
status    finished
net PnL   13.595363 USDC  (return 0.013595363)
trading   6 trades, win rate 0.666666666, max drawdown 0.004747886, exposure 0.157638888
fees      2.424621 USDC; at 2x fees net PnL 11.171029
guardrails met (trades ok, symbols ok, drawdown ok)
L1 regrade reproduced byte for byte
```

The dev window fell 2.3% from open to close, so this result is not a long-bias artefact.

## Robustness check

The same rule set was replayed on four synthetic variants of the dev window — the original, a
price-mirrored (inverted) series, a detrended series, and a series with the drift flipped — where
it returned +13.60 / +1.59 / +2.77 / +0.33 USDC, positive in all four. Configurations tuned only
to the dev window (higher dev PnL, e.g. +11.44 at a shorter cooldown) went negative on the
inverted series; they were rejected for that reason.

## Layout

- `main.py`: the bot (standard library only, deterministic, no network, no wall clock)
- `vendor/makefun_bars.py`: the kit's protocol shim, copied as the kit README instructs

Run locally from inside the unpacked kit:

```sh
node cli/makefun.mjs grade-local --kit . --bot /path/to/this/repo --driver docker
```
