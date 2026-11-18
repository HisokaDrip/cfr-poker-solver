"""
Rules for the two toy pokers everyone uses to test equilibrium solvers.

A game here is just a bag of pure functions over immutable states, so the
tree compiler (tree.py) can walk it once and never touch these again.

Kuhn:  3 cards (J Q K), one card each, ante 1, a single bet of 1.
Leduc: 6 cards (J J Q Q K K), one private card each, ante 1, two betting
       rounds (bet 2 then 4, max two raises per round), one public card
       turned between them. Pairing the board beats everything.
"""

from itertools import product

RANKS = "JQK"


class Kuhn:
    name = "kuhn"
    actions_label = {"p": "pass", "b": "bet"}

    # state = (cards, history); cards is None until the deal
    def root(self):
        return (None, "")

    def is_chance(self, s):
        return s[0] is None

    def chance_outcomes(self, s):
        deals = [(a, b) for a in range(3) for b in range(3) if a != b]
        return [((d, ""), 1 / len(deals)) for d in deals]

    def is_terminal(self, s):
        return s[1] in ("pp", "bp", "bb", "pbp", "pbb")

    def player(self, s):
        return len(s[1]) % 2

    def actions(self, s):
        return ["p", "b"]

    def next(self, s, a):
        return (s[0], s[1] + a)

    def payoff(self, s):
        """Chips won by player 0."""
        cards, h = s
        if h == "bp":
            return 1.0
        if h == "pbp":
            return -1.0
        stake = 2.0 if "b" in h else 1.0
        return stake if cards[0] > cards[1] else -stake

    def infoset(self, s):
        p = self.player(s)
        return RANKS[s[0][p]] + ":" + s[1]


class Leduc:
    name = "leduc"
    actions_label = {"f": "fold", "c": "check/call", "r": "bet/raise"}
    bet_sizes = (2, 4)
    max_raises = 2

    # state = (private, public, rounds)
    #   private: (rank0, rank1) or None
    #   public:  rank or None
    #   rounds:  tuple of betting strings, one per round started
    def root(self):
        return (None, None, ("",))

    def is_chance(self, s):
        private, public, rounds = s
        if private is None:
            return True
        # first round closed, board not out yet
        return public is None and len(rounds) == 1 and self._round_over(rounds[0])

    def chance_outcomes(self, s):
        private, public, rounds = s
        if private is None:
            # deal by rank instead of by card: same game, ~3x smaller tree
            out = []
            for a, b in product(range(3), repeat=2):
                p = 2 / 6 * ((1 if a == b else 2) / 5)
                out.append((((a, b), None, ("",)), p))
            return out
        left = [2 - private.count(r) for r in range(3)]
        return [((private, r, rounds + ("",)), left[r] / 4) for r in range(3) if left[r]]

    @staticmethod
    def _round_over(h):
        # any check/call after the first action closes the round
        return len(h) >= 2 and h[-1] == "c"

    def is_terminal(self, s):
        rounds = s[2]
        if rounds[-1].endswith("f"):
            return True
        return len(rounds) == 2 and self._round_over(rounds[1])

    def player(self, s):
        return len(s[2][-1]) % 2

    def actions(self, s):
        h = s[2][-1]
        raises = h.count("r")
        facing = raises > 0 and h[-1] == "r"
        acts = ["f", "c"] if facing else ["c"]
        if raises < self.max_raises:
            acts.append("r")
        return acts

    def next(self, s, a):
        private, public, rounds = s
        return (private, public, rounds[:-1] + (rounds[-1] + a,))

    def contributions(self, rounds):
        put = [1, 1]
        for size, h in zip(self.bet_sizes, rounds):
            for i, a in enumerate(h):
                p = i % 2
                if a == "r":
                    put[p] = max(put) + size
                elif a == "c":
                    put[p] = max(put)
        return put

    def payoff(self, s):
        private, public, rounds = s
        put = self.contributions(rounds)
        last = rounds[-1]
        if last.endswith("f"):
            folder = (len(last) - 1) % 2
            return -put[0] if folder == 0 else put[1]
        s0, s1 = self.hand_strength(private[0], public), self.hand_strength(private[1], public)
        if s0 == s1:
            return 0.0
        return float(put[1]) if s0 > s1 else -float(put[0])

    @staticmethod
    def hand_strength(rank, public):
        return 10 + rank if rank == public else rank

    def infoset(self, s):
        private, public, rounds = s
        p = self.player(s)
        board = RANKS[public] if public is not None else ""
        return RANKS[private[p]] + board + ":" + "/".join(rounds)


GAMES = {"kuhn": Kuhn, "leduc": Leduc}


def make_game(name):
    try:
        return GAMES[name]()
    except KeyError:
        raise SystemExit(f"unknown game {name!r}, pick one of {sorted(GAMES)}")
