import argparse
import json
import math
import sys
import time

from .exploit import expected_value, exploitability
from .games import make_game
from .play import play
from .solvers import SOLVERS, make_solver
from .tree import compile_tree


def cmd_solve(args):
    game = make_game(args.game)
    solver = make_solver(args.algo, game)
    st = solver.tree.stats()
    print(f"{game.name}: {st['infosets']} infosets, {st['decision']} decision nodes, {st['terminal']} terminals")
    print(f"{'iter':>7} {'secs':>6} {'ev(p0)':>9} {'exploit (mbb/g)':>16}")

    def report(sv, secs):
        e = exploitability(sv.tree) * 1000
        print(f"{sv.t:>7} {secs:>6.1f} {expected_value(sv.tree):>9.5f} {e:>16.3f}")

    solver.solve(args.iters, report, args.every or max(args.iters // 10, 1))
    if args.iters % (args.every or max(args.iters // 10, 1)):
        report(solver, 0.0)

    table = solver.tree.average_strategy()
    if args.save:
        with open(args.save, "w") as f:
            json.dump({"game": game.name, "algo": args.algo, "iters": args.iters, "strategy": table}, f, indent=1)
        print(f"saved strategy to {args.save}")
    if args.show:
        show_table(game, table, args.show)


def show_table(game, table, limit):
    print()
    # group by betting history so the dump reads like a decision chart
    order = sorted(table, key=lambda k: (len(k.split(":")[1]), k.split(":")[1], "JQK".index(k[0]), k))
    for key in order:
        row = table[key]
        if game.name == "leduc" and limit != "all" and "/" in key:
            continue  # keep the leduc dump to the preflop spots
        cells = "  ".join(f"{game.actions_label[a]:>10} {p:5.3f}" for a, p in row.items())
        print(f"  {key:<14} {cells}")


def chart(series, width=56, height=14):
    """log-log ascii plot of exploitability curves; series = {name: [(t, e)]}"""
    marks = "o+*x"
    pts = [(t, e) for s in series.values() for t, e in s if e > 0]
    lo = math.log10(min(e for _, e in pts))
    hi = math.log10(max(e for _, e in pts))
    tmax = max(t for t, _ in pts)
    grid = [[" "] * width for _ in range(height)]
    for m, s in zip(marks, series.values()):
        for t, e in s:
            x = min(int(math.log(t) / math.log(tmax or 2) * (width - 1)), width - 1)
            y = int((hi - math.log10(e)) / (hi - lo or 1) * (height - 1))
            grid[y][x] = m
    lines = []
    for y, row in enumerate(grid):
        val = 10 ** (hi - y / (height - 1) * (hi - lo))
        label = f"{val:8.2f} |" if y % 3 == 0 or y == height - 1 else "         |"
        lines.append(label + "".join(row))
    lines.append("         +" + "-" * width)
    lines.append(f"          1{'iterations (log)':^{width - 8}}{tmax}")
    lines.append("          " + "   ".join(f"{m} {name}" for m, name in zip(marks, series)))
    return "\n".join(lines)


def cmd_bench(args):
    game = make_game(args.game)
    checkpoints = sorted({max(1, int(round(args.iters ** (k / 12)))) for k in range(13)})
    series = {}
    print(f"exploitability in mbb/g on {game.name}")
    header = f"{'iter':>6}" + "".join(f"{name:>11}" for name in SOLVERS)
    rows = {c: [] for c in checkpoints}
    times = {}
    for name in SOLVERS:
        solver = make_solver(name, compile_tree(game))
        series[name] = []
        start = time.perf_counter()
        spent_eval = 0.0
        for c in checkpoints:
            solver.solve(c - solver.t)
            t0 = time.perf_counter()
            e = exploitability(solver.tree) * 1000
            spent_eval += time.perf_counter() - t0
            series[name].append((c, e))
            rows[c].append(e)
        times[name] = time.perf_counter() - start - spent_eval
    print(header)
    for c in checkpoints:
        print(f"{c:>6}" + "".join(f"{e:>11.3f}" for e in rows[c]))
    print(f"{'secs':>6}" + "".join(f"{times[n]:>11.1f}" for n in SOLVERS))
    print()
    print(chart(series))


def cmd_play(args):
    game = make_game(args.game)
    if args.strategy:
        with open(args.strategy) as f:
            blob = json.load(f)
        if blob["game"] != game.name:
            sys.exit(f"{args.strategy} is a {blob['game']} strategy")
        table = blob["strategy"]
    else:
        print(f"solving {game.name} with cfr+ for {args.iters} iterations first...")
        solver = make_solver("cfr+", game).solve(args.iters)
        print(f"done, exploitability {exploitability(solver.tree) * 1000:.2f} mbb/g. good luck.")
        table = solver.tree.average_strategy()
    total, n = play(game, table, hands=args.hands, seed=args.seed)
    if n:
        print(f"final: {total:+g} chips over {n} hands ({total / n:+.3f}/hand)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pokercfr", description="CFR solvers for Kuhn and Leduc poker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("solve", help="run one solver and report convergence")
    p.add_argument("game", choices=["kuhn", "leduc"])
    p.add_argument("--algo", default="cfr+", choices=sorted(SOLVERS))
    p.add_argument("--iters", type=int, default=1000)
    p.add_argument("--every", type=int, default=0)
    p.add_argument("--save", help="write the average strategy to this json file")
    p.add_argument("--show", nargs="?", const="some", help="print the strategy table ('all' for every leduc spot)")
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("bench", help="compare cfr / cfr+ / dcfr convergence")
    p.add_argument("game", choices=["kuhn", "leduc"])
    p.add_argument("--iters", type=int, default=1000)
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("play", help="play against the solved strategy")
    p.add_argument("game", choices=["kuhn", "leduc"])
    p.add_argument("--strategy", help="json from `solve --save` (otherwise solves on the spot)")
    p.add_argument("--iters", type=int, default=500)
    p.add_argument("--hands", type=int)
    p.add_argument("--seed", type=int)
    p.set_defaults(func=cmd_play)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
