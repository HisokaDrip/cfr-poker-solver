import math

import pytest

from pokercfr import Kuhn, Leduc, compile_tree


def test_kuhn_payoffs():
    g = Kuhn()
    K, Q, J = 2, 1, 0
    assert g.payoff(((K, J), "pp")) == 1
    assert g.payoff(((J, K), "pp")) == -1
    assert g.payoff(((J, K), "bp")) == 1       # bluff gets through
    assert g.payoff(((K, J), "pbp")) == -1     # p0 folds to the bet
    assert g.payoff(((Q, K), "pbb")) == -2
    assert g.payoff(((K, Q), "bb")) == 2


def test_leduc_contributions():
    g = Leduc()
    assert g.contributions(("",)) == [1, 1]
    assert g.contributions(("r",)) == [3, 1]
    assert g.contributions(("rrc",)) == [5, 5]
    assert g.contributions(("crrc", "rc")) == [9, 9]
    assert g.contributions(("cc", "crr")) == [9, 5]  # check, bet 4, raise to 9


def test_leduc_raise_cap():
    g = Leduc()
    s = ((0, 1), None, ("rr",))
    assert g.actions(s) == ["f", "c"]
    assert g.actions(((0, 1), None, ("",))) == ["c", "r"]
    assert g.actions(((0, 1), None, ("r",))) == ["f", "c", "r"]


def test_leduc_showdown_and_folds():
    g = Leduc()
    J, Q, K = 0, 1, 2
    # pairing the board beats a higher card
    assert g.payoff(((J, K), J, ("cc", "cc"))) == 1
    assert g.payoff(((Q, K), J, ("rc", "rc"))) == -7
    assert g.payoff(((K, K), J, ("rc", "rc"))) == 0  # split
    assert g.payoff(((J, K), None, ("rf",))) == 1     # p1 folds round one
    assert g.payoff(((K, J), Q, ("cc", "crf"))) == -1  # p0 checks, then folds to the bet
    assert g.payoff(((J, K), Q, ("rrc", "rf"))) == 5   # p1 folds after calling 5 preflop


def test_chance_probs_sum_to_one():
    for g in (Kuhn(), Leduc()):
        tree = compile_tree(g)
        for node in tree.nodes:
            if node.probs:
                assert math.isclose(sum(node.probs), 1.0)


def test_leduc_rank_deal_matches_card_deal():
    # P(both dealt a jack) = 2/6 * 1/5
    out = dict(Leduc().chance_outcomes(Leduc().root()))
    assert math.isclose(out[((0, 0), None, ("",))], 1 / 15)
    assert math.isclose(out[((0, 1), None, ("",))], 2 / 15)
    board = dict(Leduc().chance_outcomes(((0, 0), None, ("cc",))))
    assert len(board) == 2  # both jacks are gone


@pytest.mark.parametrize("game, infosets", [(Kuhn(), 12), (Leduc(), 288)])
def test_infoset_counts(game, infosets):
    assert compile_tree(game).stats()["infosets"] == infosets
