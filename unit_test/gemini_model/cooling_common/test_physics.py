"""Reusable model SI helpers, independent of challenge-plant dispatch."""

import numpy as np
import pytest

from gemini_model.cooling_common.physics import counterflow_hx, hx_conductance_w_k, pump_power_w


def test_hx_both_terminal_approaches_under_unequal_flows():
    """Large UA still respects both terminal approach constraints."""
    r = counterflow_hx(85, 65, 1e5, 2e5, 1e9, approach_k=5)
    assert r["power_transfer_w"] == pytest.approx(1.5e6)
    assert 85 - r["outlet_b_c"] >= 5
    assert r["outlet_a_c"] - 65 >= 5
    assert (85 - r["outlet_a_c"]) * 1e5 == pytest.approx((r["outlet_b_c"] - 65) * 2e5)


def test_equal_c_limit_is_continuous():
    """Counterflow Cr=1 branch agrees near the equal-capacity limit."""
    exact = hx_conductance_w_k(41800, 41800, 20000)
    near = hx_conductance_w_k(41800, 41800 * (1 + 1e-10), 20000)
    assert exact == pytest.approx(near, rel=1e-9)


def test_vector_pump_units_and_bad_efficiency():
    """Pressure is differential Pa, never reservoir bar(g)."""
    p = pump_power_w(np.array([0, 100]) / 3600, 1e5, 0.7)
    np.testing.assert_allclose(p, [0, 3968.253968253968])
    for eta in [0, -0.1, 1.1, float("nan")]:
        with pytest.raises(ValueError):
            pump_power_w(1, 1, eta)
