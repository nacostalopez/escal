"""Tests for app/services/forecasting.py::linear_forecast (pure function,
no DB needed)."""
from app.services.forecasting import linear_forecast


class TestLinearForecast:
    def test_perfectly_linear_sequence_extrapolates_exactly(self):
        # values[i] = i -> next points should be 5, 6, 7
        result = linear_forecast([0.0, 1.0, 2.0, 3.0, 4.0], periods_ahead=3)
        assert result == [5.0, 6.0, 7.0]

    def test_flat_series_predicts_the_same_constant(self):
        result = linear_forecast([10.0, 10.0, 10.0, 10.0], periods_ahead=3)
        assert result == [10.0, 10.0, 10.0]

    def test_downward_trend_keeps_declining(self):
        result = linear_forecast([100.0, 90.0, 80.0, 70.0], periods_ahead=2)
        assert result == [60.0, 50.0]

    def test_single_value_repeats_it(self):
        result = linear_forecast([42.0], periods_ahead=3)
        assert result == [42.0, 42.0, 42.0]

    def test_empty_input_returns_zeros(self):
        result = linear_forecast([], periods_ahead=3)
        assert result == [0.0, 0.0, 0.0]

    def test_noisy_but_generally_upward_series(self):
        # Not perfectly linear — just confirm the fit trends the right way
        # rather than asserting exact values (any reasonable OLS fit works).
        result = linear_forecast([10.0, 12.0, 11.0, 15.0, 14.0, 18.0], periods_ahead=2)
        assert result[1] > result[0] > 18.0
