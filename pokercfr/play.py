"""Play heads-up against a solved strategy in the terminal."""

import random

from .games import RANKS


def _sample(pairs, rng):
    r = rng.random()
    acc = 0.0
    for item, p in pairs:
        acc += p
        if r < acc:
            return item
    return pairs[-1][0]


def bot_action(game, state, table, rng):
    acts = game.actions(state)
    row = table.get(game.infoset(state))
    if not row:
        return rng.choice(acts)
    return _sample([(a, row.get(a, 0.0)) for a in acts], rng)


def describe(game, state, seat):
    if game.name == "kuhn":
        cards, h = state
        return f"you hold {RANKS[cards[seat]]}   betting: {h or '-'}"
    private, public, rounds = state
    board = RANKS[public] if public is not None else "?"
    pot = sum(game.contributions(rounds))
    return f"you hold {RANKS[private[seat]]}   board {board}   pot {pot}   betting: {'/'.join(rounds) or '-'}"


def play_hand(game, table, human_seat, rng, ask=input, say=print):
    s = game.root()
    while not game.is_terminal(s):
        if game.is_chance(s):
            s = _sample(game.chance_outcomes(s), rng)
            continue
        acts = game.actions(s)
        if game.player(s) == human_seat:
            say(describe(game, s, human_seat))
            menu = "  ".join(f"[{a}] {game.actions_label[a]}" for a in acts)
            a = ""
            while a not in acts:
                a = ask(f"  {menu} > ").strip().lower()[:1]
            s = game.next(s, a)
        else:
            a = bot_action(game, s, table, rng)
            say(f"  bot: {game.actions_label[a]}")
            s = game.next(s, a)

    won = game.payoff(s) * (1 if human_seat == 0 else -1)
    bot_card = RANKS[s[0][1 - human_seat]]  # private cards live in s[0] for both games
    say(f"  bot had {bot_card}. you {'won' if won > 0 else 'lost' if won < 0 else 'split'} {abs(won):g}")
    return won


def play(game, table, hands=None, seed=None, ask=input, say=print):
    rng = random.Random(seed)
    total, n = 0.0, 0
    try:
        while hands is None or n < hands:
            seat = n % 2  # swap seats every hand, position matters a lot here
            say(f"\n-- hand {n + 1} (you are {'first' if seat == 0 else 'second'} to act) --")
            total += play_hand(game, table, seat, rng, ask, say)
            n += 1
            say(f"  running total: {total:+g} over {n} hands")
    except (EOFError, KeyboardInterrupt):
        say("")
    return total, n
