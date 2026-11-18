import json
import random

from pokercfr import Kuhn, Leduc, compile_tree, exploitability, make_solver
from pokercfr.__main__ import main
from pokercfr.play import bot_action, play


def test_bot_follows_a_pure_strategy():
    g = Kuhn()
    rng = random.Random(0)
    table = {"K:": {"p": 0.0, "b": 1.0}}
    assert all(bot_action(g, ((2, 0), ""), table, rng) == "b" for _ in range(50))


def test_scripted_session_adds_up():
    g = Leduc()
    table = make_solver("cfr+", g).solve(50).tree.average_strategy()
    lines = []
    total, n = play(g, table, hands=20, seed=3, ask=lambda _: "c", say=lines.append)
    assert n == 20
    results = [l for l in lines if "you won" in l or "you lost" in l or "you split" in l]
    assert len(results) == 20
    assert lines[-1].startswith("  running total:") and f"{total:+g}" in lines[-1]


def test_solve_save_and_reload(tmp_path, capsys):
    out = tmp_path / "kuhn.json"
    main(["solve", "kuhn", "--iters", "400", "--save", str(out)])
    blob = json.loads(out.read_text())
    assert blob["game"] == "kuhn" and len(blob["strategy"]) == 12

    tree = compile_tree(Kuhn())
    tree.load_strategy(blob["strategy"])
    assert exploitability(tree) < 0.005
    assert "saved strategy" in capsys.readouterr().out


def test_bench_runs(capsys):
    main(["bench", "kuhn", "--iters", "60"])
    out = capsys.readouterr().out
    assert "cfr+" in out and "iterations" in out
