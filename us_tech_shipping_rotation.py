import math
import pandas as pd
from panda_backtest.api.api import *
from panda_backtest.api.stock_us_api import *


def _valid_price(value):
    price = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(price):
        return None
    price = float(price)
    return price if math.isfinite(price) and price > 0 else None


def _moving_average(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / float(window)


def _group_signal(context, group):
    ratios = []
    for symbol in context.groups[group]:
        closes = context.closes[symbol]
        short_ma = _moving_average(closes, context.short_window)
        long_ma = _moving_average(closes, context.long_window)
        if short_ma is None or long_ma is None or short_ma <= long_ma:
            return None
        ratios.append(short_ma / long_ma - 1.0)
    return sum(ratios) / len(ratios)


def _held_symbols(account, symbols):
    held = []
    for symbol in symbols:
        position = account.positions.get(symbol)
        quantity = 0 if position is None else int(getattr(position, "quantity", 0) or 0)
        if quantity > 0:
            held.append(symbol)
    return held


def _sell_group(context, account, group):
    for symbol in context.groups[group]:
        position = account.positions.get(symbol)
        sellable = 0 if position is None else int(getattr(position, "sellable", 0) or 0)
        if sellable > 0:
            order_shares(
                context.account,
                symbol,
                -sellable,
                style=MarketOrderStyle,
                remark="Tech-shipping rotation exit",
            )


def _buy_group(context, account, group, prices):
    cash = float(getattr(account, "cash", 0) or 0)
    target_value = cash * context.weight_per_symbol
    for symbol in context.groups[group]:
        quantity = int(target_value // prices[symbol])
        if quantity > 0:
            order_shares(
                context.account,
                symbol,
                quantity,
                style=MarketOrderStyle,
                remark="Tech-shipping rotation entry",
            )


def init_market_data(context):
    context.account = "15032863"
    context.groups = {
        "tech": ["AAPL.NB", "NVDA.NB"],
        "shipping": ["ZIM.NB", "FRO.NB"],
    }
    context.universe = context.groups["tech"] + context.groups["shipping"]
    context.short_window = 5
    context.long_window = 20
    context.weight_per_symbol = 0.40
    context.confirm_days = 2
    context.closes = {symbol: [] for symbol in context.universe}
    context.last_trade_date = None
    context.candidate_group = None
    context.candidate_days = 0
    context.last_exit_date = None

    warmup_start = (
        pd.Timestamp(str(context.run_info.start_date)) - pd.Timedelta(days=120)
    ).strftime("%Y%m%d")
    warmup_end = (
        pd.Timestamp(str(context.run_info.start_date)) - pd.Timedelta(days=1)
    ).strftime("%Y%m%d")
    history = stock_api_quotation(
        symbol_list=context.universe,
        start_date=warmup_start,
        end_date=warmup_end,
        fields=["symbol", "date", "close"],
        period="1d",
    )
    if history is None or history.empty:
        return
    for symbol in context.universe:
        rows = history[history["symbol"] == symbol].sort_values("date")
        for close in rows["close"].tolist():
            value = _valid_price(close)
            if value is not None:
                context.closes[symbol].append(value)
        context.closes[symbol] = context.closes[symbol][-(context.long_window + 2):]


def initialize(context):
    init_market_data(context)


def handle_data(context, data):
    prices = {}
    trade_date = None
    for symbol in context.universe:
        bar = data[symbol]
        if bar is None:
            return
        price = _valid_price(getattr(bar, "close", None))
        current_date = getattr(bar, "trade_date", None)
        if price is None or current_date is None:
            return
        if trade_date is None:
            trade_date = current_date
        elif trade_date != current_date:
            return
        prices[symbol] = price

    if context.last_trade_date == trade_date:
        return
    account = context.stock_account_dict.get(context.account)
    if account is None:
        return

    for symbol in context.universe:
        context.closes[symbol].append(prices[symbol])
        context.closes[symbol] = context.closes[symbol][-(context.long_window + 2):]
        if len(context.closes[symbol]) < context.long_window:
            return
    context.last_trade_date = trade_date

    scores = {}
    for group in context.groups:
        score = _group_signal(context, group)
        if score is not None:
            scores[group] = score
    candidate = None
    if len(scores) == 1:
        candidate = list(scores.keys())[0]
    elif len(scores) == 2:
        candidate = max(scores, key=scores.get)

    if candidate == context.candidate_group:
        context.candidate_days += 1
    else:
        context.candidate_group = candidate
        context.candidate_days = 1
    confirmed = candidate if context.candidate_days >= context.confirm_days else None

    tech_held = _held_symbols(account, context.groups["tech"])
    shipping_held = _held_symbols(account, context.groups["shipping"])
    active_group = None
    if tech_held and not shipping_held:
        active_group = "tech"
    elif shipping_held and not tech_held:
        active_group = "shipping"

    target_symbols = [] if confirmed is None else context.groups[confirmed]
    print(
        "[rotation] date={} candidate={} confirmed={} active={} eligible_count={} target_symbols={}".format(
            trade_date,
            candidate,
            confirmed,
            active_group,
            len(scores),
            target_symbols,
        )
    )

    if tech_held and shipping_held:
        _sell_group(context, account, "tech")
        _sell_group(context, account, "shipping")
        context.last_exit_date = trade_date
        return

    if active_group is not None and confirmed != active_group:
        _sell_group(context, account, active_group)
        context.last_exit_date = trade_date
        return

    if active_group is None and confirmed is not None and context.last_exit_date != trade_date:
        _buy_group(context, account, confirmed, prices)
