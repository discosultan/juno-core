import logging
from collections import defaultdict
from decimal import Decimal
from typing import Callable, Dict, List, NamedTuple, Tuple

import numpy as np
import pandas as pd

from juno.math import floor_multiple
from juno.time import DAY_MS
from juno.utils import unpack_symbol

from .common import TradingSummary

Operator = Callable[[Decimal, Decimal], Decimal]

_log = logging.getLogger(__name__)


class Statistics(NamedTuple):
    performance: pd.Series
    a_returns: pd.Series
    g_returns: pd.Series
    neg_g_returns: pd.Series

    total_return: float
    annualized_return: float
    annualized_volatility: float
    annualized_downside_risk: float
    sharpe_ratio: float
    sortino_ratio: float
    cagr: float


class PortfolioStatistics(NamedTuple):
    performance: pd.Series
    a_returns: pd.Series
    g_returns: pd.Series
    neg_g_returns: pd.Series

    total_return: float
    annualized_return: float
    annualized_volatility: float
    annualized_downside_risk: float
    sharpe_ratio: float
    sortino_ratio: float
    cagr: float

    alpha: float
    beta: float


def get_benchmark_statistics(prices: List[Decimal]) -> Statistics:
    performance = pd.Series([float(p) for p in prices])
    return _calculate_statistics(performance)


def get_portfolio_statistics(
    benchmark_stats: Statistics,
    fiat_daily_prices: Dict[str, List[Decimal]],
    summary: TradingSummary
) -> PortfolioStatistics:
    start_day = floor_multiple(summary.start, DAY_MS)
    end_day = floor_multiple(summary.end, DAY_MS)
    # length_days = (end_day - start_day) / DAY_MS

    # assert len(quote_fiat_daily) == length_days
    # assert all(len(c) == length_days for c in base_quote_daily_prices.values())
    # TODO: We don't support other quote yet.
    # assert all(unpack_symbol(s)[1] == 'btc' for s in base_quote_daily_prices.keys())

    trades = _get_trades_from_summary(summary)
    asset_performance = _get_asset_performance(
        summary, start_day, end_day, fiat_daily_prices, trades
    )
    portfolio_performance = pd.Series(
        [float(sum(v for v in apd.values())) for apd in asset_performance]
    )

    portfolio_stats = _calculate_statistics(portfolio_performance)
    return PortfolioStatistics(
        *portfolio_stats,
        *_calculate_alpha_beta(benchmark_stats, portfolio_stats),
    )


def _get_trades_from_summary(
    summary: TradingSummary,
) -> Dict[int, List[Tuple[str, Decimal]]]:
    trades: Dict[int, List[Tuple[str, Decimal]]] = defaultdict(list)
    for pos in summary.positions:
        assert pos.closing_fills
        base_asset, quote_asset = unpack_symbol(pos.symbol)
        # Open.
        time = floor_multiple(pos.time, DAY_MS)
        day_trades = trades[time]
        day_trades.append((quote_asset, -pos.cost))
        day_trades.append((base_asset, +pos.base_gain))
        # Close.
        time = floor_multiple(pos.closing_time, DAY_MS)
        day_trades = trades[time]
        day_trades.append((base_asset, -pos.base_cost))
        day_trades.append((quote_asset, +pos.gain))
    return trades


def _get_asset_performance(
    summary: TradingSummary,
    start_day: int,
    end_day: int,
    market_data: Dict[str, List[Decimal]],
    trades: Dict[int, List[Tuple[str, Decimal]]]
) -> List[Dict[str, Decimal]]:
    asset_holdings: Dict[str, Decimal] = defaultdict(lambda: Decimal('0.0'))
    # TODO: Support other than BTC quote.
    asset_holdings['btc'] = summary.quote

    asset_performance: List[Dict[str, Decimal]] = []

    i = 0
    for time_day in range(start_day, end_day, DAY_MS):
        # Update holdings.
        day_trades = trades.get(time_day)
        if day_trades:
            for asset, size in day_trades:
                asset_holdings[asset] = asset_holdings[asset] + size

        # Update asset performance (mark-to-market portfolio).
        asset_performance_day = {k: Decimal('0.0') for k in market_data.keys()}
        for asset in market_data.keys():
            asset_fiat_value = market_data[asset][i]
            asset_performance_day[asset] = asset_holdings[asset] * asset_fiat_value

        asset_performance.append(asset_performance_day)
        i += 1

    return asset_performance


def _calculate_statistics(performance: pd.Series) -> Statistics:
    a_returns = performance.pct_change().dropna()
    g_returns = np.log(a_returns + 1)
    neg_g_returns = g_returns[g_returns < 0].dropna()

    # Compute statistics.
    total_return = performance.iloc[-1] / performance.iloc[0] - 1
    annualized_return = 365 * g_returns.mean()
    annualized_volatility = np.sqrt(365) * g_returns.std()
    annualized_downside_risk = np.sqrt(365) * neg_g_returns.std()
    sharpe_ratio = annualized_return / annualized_volatility
    sortino_ratio = annualized_return / annualized_downside_risk
    cagr = (
        (performance.iloc[-1] / performance.iloc[0])
        ** (1 / (performance.size / 365))
    ) - 1

    return Statistics(
        performance=performance,
        a_returns=a_returns,
        g_returns=g_returns,
        neg_g_returns=neg_g_returns,
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        annualized_downside_risk=annualized_downside_risk,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        cagr=cagr
    )


def _calculate_alpha_beta(
    benchmark_stats: Statistics, portfolio_stats: Statistics
) -> Tuple[float, float]:
    covariance_matrix = pd.concat(
        [portfolio_stats.g_returns, benchmark_stats.g_returns], axis=1
    ).dropna().cov()
    beta = covariance_matrix.iloc[0].iloc[1] / covariance_matrix.iloc[1].iloc[1]
    alpha = portfolio_stats.annualized_return - (beta * 365 * benchmark_stats.g_returns.mean())

    return alpha, beta
