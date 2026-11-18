"""
Flatten a game into a plain node graph once, up front.

Calling the rule functions on every CFR iteration was ~6x slower than walking
pre-built nodes, and the tree for Leduc is tiny (a few thousand decision
nodes once you deal by rank), so there's no reason not to.
"""

TERMINAL, CHANCE, DECISION = 0, 1, 2


class Node:
    __slots__ = ("kind", "idx", "payoff", "children", "probs", "player", "info", "history")

    def __init__(self, kind, idx):
        self.kind = kind
        self.idx = idx
        self.payoff = 0.0
        self.children = ()
        self.probs = ()
        self.player = -1
        self.info = -1
        self.history = None


class InfoSet:
    __slots__ = ("key", "player", "actions", "regret", "strategy_sum", "current")

    def __init__(self, key, player, actions):
        n = len(actions)
        self.key = key
        self.player = player
        self.actions = actions
        self.regret = [0.0] * n
        self.strategy_sum = [0.0] * n
        self.current = [1.0 / n] * n

    def average(self):
        total = sum(self.strategy_sum)
        n = len(self.actions)
        if total <= 0:
            return [1.0 / n] * n
        return [x / total for x in self.strategy_sum]


class GameTree:
    def __init__(self, game):
        self.game = game
        self.nodes = []
        self.infosets = []
        self.index = {}  # infoset key -> position in self.infosets
        self.root = self._build(game.root())

    def _new(self, kind):
        node = Node(kind, len(self.nodes))
        self.nodes.append(node)
        return node

    def _build(self, s):
        g = self.game
        if g.is_terminal(s):
            node = self._new(TERMINAL)
            node.payoff = g.payoff(s)
            return node
        if g.is_chance(s):
            node = self._new(CHANCE)
            outcomes = g.chance_outcomes(s)
            node.probs = tuple(p for _, p in outcomes)
            node.children = tuple(self._build(nxt) for nxt, _ in outcomes)
            return node

        node = self._new(DECISION)
        node.player = g.player(s)
        node.history = s
        acts = g.actions(s)
        key = g.infoset(s)
        if key not in self.index:
            self.index[key] = len(self.infosets)
            self.infosets.append(InfoSet(key, node.player, acts))
        elif self.infosets[self.index[key]].actions != acts:
            # would mean the rules leak hidden info into the action set
            raise ValueError(f"inconsistent actions at infoset {key}")
        node.info = self.index[key]
        node.children = tuple(self._build(g.next(s, a)) for a in acts)
        return node

    def stats(self):
        kinds = [0, 0, 0]
        for n in self.nodes:
            kinds[n.kind] += 1
        return {
            "nodes": len(self.nodes),
            "terminal": kinds[TERMINAL],
            "chance": kinds[CHANCE],
            "decision": kinds[DECISION],
            "infosets": len(self.infosets),
        }

    def average_strategy(self):
        return {I.key: dict(zip(I.actions, I.average())) for I in self.infosets}

    def load_strategy(self, table):
        """Load a {infoset: {action: prob}} table into strategy_sum so that
        average() reproduces it. Handy for evaluating saved strategies."""
        for I in self.infosets:
            row = table.get(I.key)
            if row is not None:
                I.strategy_sum = [float(row.get(a, 0.0)) for a in I.actions]


def compile_tree(game):
    return GameTree(game)
