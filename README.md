# btc-race bot

make.fun `btc-race-24h` entry. One symbol (cbBTC/USDC), 1-minute bars, 1,000 USDC of paper
capital, long only, 10,000 USDC of depth per bar.

## What it does

The replay costs a full-size round trip about 27 bp: 4 bp of fee each way, 2 bp of slippage each
way, and roughly 8 bp of constant-product impact on 1,000 USDC against a pool that carries about
1.3M USDC. One-minute volatility on this pair is about 5 bp, so a minute-scale signal cannot fund
a trade. The bot therefore buys once, at the first tradeable bar, and rides the one sustained leg
a 24-hour window usually contains:

- enter: full cash at the first bar after warmup (`buy`, all of `state.cash`)
- hold: track the running peak close
- exit: on either a 0.8% give-back from the peak, or a close under the 360-minute mean
- never re-enter: a second seat pays the whole round trip again

`max_slippage_bps` is 500 so a stop can still fill after a fast move.

## Dev-window result (kit `btc-race-24h-20261112-1439`, `--driver docker`)

```
status    finished
net PnL   5.951376 USDC  (return 0.005951376)
trading   2 trades, win rate 1.0, max drawdown 0.006649271, exposure 0.302083333
fees      0.802542 USDC; at 2x fees net PnL 5.147360
guardrails met (trades ok, symbols ok, drawdown ok)
```

## Layout

- `main.py`: the bot (standard library only, deterministic, no network, no wall clock)
- `vendor/makefun_bars.py`: the kit's protocol shim, copied as the kit README instructs

Run locally from inside the unpacked kit:

```sh
node cli/makefun.mjs grade-local --kit . --bot /path/to/this/repo --driver docker
```
