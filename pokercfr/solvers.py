"""
Counterfactual regret minimisation, three flavours.

All three share the same full-width traversal with alternating updates;
they only differ in what happens to the regrets and the average-strategy
accumulator after each player's pass:

  CFR    plain regret matching, uniform averaging     (Zinkevich et al. 2007)
  CFR+   regrets clipped at zero, linear averaging    (Tammelin 2014)
  DCFR   positive/negative regrets discounted at
         different rates, average decays by (t/t+1)^g (Brown & Sandholm 2019)

In practice on Leduc: CFR+ and DCFR get to ~1 mbb/g in a few hundred
iterations, vanilla CFR needs thousands. See `python -m pokercfr bench`.
"""

import time

from .tree import CHANCE, TERMINAL, compile_tree


class CFR:
    name = "cfr"

    def __init__(self, tree):
        self.tree = tree
        self.t = 0

    # -- hooks the variants override ---------------------------------------
    def avg_weight(self):
        return 1.0

    def after_pass(self, player):
        pass

    # -- core --------------------------------------------------------------
    def _refresh_current(self):
        for I in self.tree.infosets:
            pos = [r if r > 0 else 0.0 for r in I.regret]
            total = sum(pos)
            if total > 0:
                I.current = [r / total for r in pos]
            else:
                I.current = [1.0 / len(pos)] * len(pos)

    def _walk(self, node, i, pi_i, pi_o, w):
        kind = node.kind
        if kind == TERMINAL:
            return node.payoff if i == 0 else -node.payoff
        if kind == CHANCE:
            v = 0.0
            for p, child in zip(node.probs, node.children):
                v += p * self._walk(child, i, pi_i, pi_o * p, w)
            return v

        I = self.tree.infosets[node.info]
        strat = I.current
        if node.player != i:
            # no "skip if s == 0" here: the subtree still holds infosets of
            # player i whose average strategy needs this iteration's update.
            # pruning it cost ~6x in exploitability at 300 iters on leduc.
            v = 0.0
            for s, child in zip(strat, node.children):
                v += s * self._walk(child, i, pi_i, pi_o * s, w)
            return v

        utils = [self._walk(child, i, pi_i * s, pi_o, w) for s, child in zip(strat, node.children)]
        v = sum(s * u for s, u in zip(strat, utils))
        regret, ssum = I.regret, I.strategy_sum
        for a in range(len(utils)):
            regret[a] += pi_o * (utils[a] - v)
            ssum[a] += w * pi_i * strat[a]
        return v

    def iterate(self):
        self.t += 1
        w = self.avg_weight()
        for player in (0, 1):
            self._refresh_current()
            self._walk(self.tree.root, player, 1.0, 1.0, w)
            self.after_pass(player)

    def solve(self, iterations, callback=None, every=0):
        start = time.perf_counter()
        for _ in range(iterations):
            self.iterate()
            if callback and every and self.t % every == 0:
                callback(self, time.perf_counter() - start)
        return self


class CFRPlus(CFR):
    name = "cfr+"
    # skipping the first few iterates in the average helps a bit, they're junk
    delay = 0

    def avg_weight(self):
        return float(max(self.t - self.delay, 0))

    def after_pass(self, player):
        for I in self.tree.infosets:
            if I.player == player:
                I.regret = [r if r > 0 else 0.0 for r in I.regret]


class DCFR(CFR):
    name = "dcfr"
    # the paper's recommended setting
    alpha, beta, gamma = 1.5, 0.0, 2.0

    def after_pass(self, player):
        t = self.t
        ta = t ** self.alpha
        pos = ta / (ta + 1)
        tb = t ** self.beta
        neg = tb / (tb + 1)
        decay = (t / (t + 1)) ** self.gamma
        for I in self.tree.infosets:
            if I.player != player:
                continue
            I.regret = [r * (pos if r > 0 else neg) for r in I.regret]
            I.strategy_sum = [x * decay for x in I.strategy_sum]


SOLVERS = {"cfr": CFR, "cfr+": CFRPlus, "dcfr": DCFR}


def make_solver(name, game_or_tree):
    tree = game_or_tree if hasattr(game_or_tree, "infosets") else compile_tree(game_or_tree)
    try:
        return SOLVERS[name](tree)
    except KeyError:
        raise SystemExit(f"unknown solver {name!r}, pick one of {sorted(SOLVERS)}")
