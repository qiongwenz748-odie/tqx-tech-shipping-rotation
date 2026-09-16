# US Tech vs Shipping 5/20 Rotation

TQX Qube daily strategy that holds one of two mutually exclusive groups:

- **Tech:** `AAPL.NB`, `NVDA.NB`
- **Shipping:** `ZIM.NB`, `FRO.NB`

## Rules

1. A group qualifies when both constituents have `MA(5) > MA(20)` for two consecutive daily bars.
2. If both groups qualify, select the one with the greater average `MA(5) / MA(20) - 1`.
3. Allocate 40% of available portfolio value to each selected symbol (80% gross exposure).
4. If the confirmed target changes or disappears, exit the active group.
5. A new group can be entered only on a later trading day, never on the same day as an exit.

## GATC backtest configuration

| Setting | Value |
| --- | --- |
| Period start | 2025-08-29 |
| Period end | 2026-08-31 |
| Initial capital | ¥10,000,000 |
| Commission multiplier | 1.00 |
| Slippage | 0.001 |
| Frequency | 1d |

## Baseline result

Backtest `#6395` reported total return **19.57%**, maximum drawdown **11.00%**, **66** trades, and final equity **¥11,957,292.53**. Using the competition drawdown floor of 3%, the displayed-score calculation is `19.57% / max(11.00%, 3.00%) = 1.78`.

## Usage

Upload `us_tech_shipping_rotation.py` to a US-market TQX Qube strategy and run it with the configuration above. The source contains no API key. Configure the research account identifier in your Qube environment before running it.

Backtests are historical simulations; do not use this repository to place trading orders.
