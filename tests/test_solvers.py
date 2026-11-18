import math

import pytest

from pokercfr import Kuhn, Leduc, exploitability, expected_value, make_solver


@pytest.mark.parametrize("algo", ["cfr", "cfr+", "dcfr"])
def test_kuhn_converges(algo):
    sv = make_solver(algo, Kuhn()).solve(3000)
    assert math.isclose(expected_value(sv.tree), -1 / 18, abs_tol=2e-3)
    assert exploitability(sv.tree) < 1e-3


def test_kuhn_lands_in_the_equilibrium_family():
    sv = make_solver("cfr+", Kuhn()).solve(5000)
    bet = {k: v["b"] for k, v in sv.tree.average_strategy().items()}
    alpha = bet["J:"]
    assert 0 <= alpha <= 1 / 3 + 1e-3
    assert math.isclose(bet["K:"], 3 * alpha, abs_tol=0.02)
    assert math.isclose(bet["Q:pb"], alpha + 1 / 3, abs_tol=0.02)
    assert math.isclose(bet["Q:b"], 1 / 3, abs_tol=0.02)
    assert math.isclose(bet["J:p"], 1 / 3, abs_tol=0.02)
    assert bet["Q:"] < 0.01 and bet["J:b"] < 0.01 and bet["K:b"] > 0.99


def test_leduc_plus_variants_beat_vanilla():
    scores = {}
    for algo in ("cfr", "cfr+", "dcfr"):
        sv = make_solver(algo, Leduc()).solve(300)
        scores[algo] = exploitability(sv.tree)
    assert scores["cfr+"] < scores["cfr"] / 5
    assert scores["dcfr"] < scores["cfr"] / 5
    assert scores["cfr+"] < 0.005  # 5 mbb/g


def test_leduc_game_value():
    # published value of leduc for the first player is about -0.0856
    sv = make_solver("dcfr", Leduc()).solve(600)
    assert math.isclose(expected_value(sv.tree), -0.0856, abs_tol=1e-3)
    assert exploitability(sv.tree) < 1e-3


def test_average_strategy_is_a_distribution():
    sv = make_solver("cfr", Leduc()).solve(20)
    for row in sv.tree.average_strategy().values():
        assert math.isclose(sum(row.values()), 1.0)
        assert all(p >= 0 for p in row.values())
