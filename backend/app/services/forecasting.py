"""Simple linear (ordinary least squares) forecasting — no numpy/pandas,
just the closed-form OLS formulas, since a trend line over daily revenue/
spend is all "forecasting simple" needs here. See app/routes/metrics.py's
FORECAST_HISTORY_SQL and the /metrics/forecast route for how this gets its
input data.
"""


def linear_forecast(values: list[float], periods_ahead: int) -> list[float]:
    """Fits a line to `values` (x = 0..len(values)-1) and extrapolates
    `periods_ahead` points beyond the last one.

    No negative-clamping here — that's a business decision for the caller
    (revenue/ad_spend can't go below 0, net_profit legitimately can).
    """
    n = len(values)
    if n == 0:
        return [0.0] * periods_ahead
    if n == 1:
        return [values[0]] * periods_ahead

    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values))
    denominator = sum((x - mean_x) ** 2 for x in range(n))
    slope = numerator / denominator if denominator else 0.0
    intercept = mean_y - slope * mean_x

    return [slope * (n - 1 + step) + intercept for step in range(1, periods_ahead + 1)]
