# cfr-poker-solver

Counterfactual regret minimisation from scratch in pure Python (no numpy,
no deps), solving Kuhn and Leduc poker to a Nash equilibrium and then letting
you play against the result in the terminal.

I wanted to actually understand how poker bots like Libratus/Pluribus get
their blueprint strategy, and the core of it is surprisingly small: walk the
game tree, track how much you *regret* not having taken each action, play in
proportion to positive regret, and average your strategies over time. The
average provably converges to an equilibrium in two-player zero-sum games.

What's in here:

- **Kuhn** (3 cards, 12 infosets) and **Leduc** (6 cards, two betting rounds,
  a public card, 288 infosets) as plain rule functions
- a tree compiler that flattens the game once so iterations don't re-run the rules
- three solvers sharing one traversal with alternating updates:
  - **CFR** - vanilla regret matching (Zinkevich et al. 2007)
  - **CFR+** - regrets floored at zero, linear averaging (Tammelin 2014)
  - **DCFR** - discounted CFR with α=1.5, β=0, γ=2 (Brown & Sandholm 2019)
- exact **exploitability**: an infoset-level best response (not the naive
  per-node max, which cheats by peeking at the opponent's card). The tests
  check it against brute-forcing every pure counter-strategy in Kuhn.
- a play mode where you sit down against the solved bot, swapping seats each hand

## running it

```
pip install -r requirements.txt   # only pytest, the solver itself has no deps

python -m pokercfr solve kuhn --iters 5000 --show
python -m pokercfr solve leduc --algo dcfr --iters 1000 --show --save leduc.json
python -m pokercfr bench leduc --iters 2000
python -m pokercfr play leduc --strategy leduc.json
python -m pytest
```

## results

Kuhn has a known closed-form family of equilibria: player one bets a jack
with some probability α ∈ [0, 1/3], bets a king with 3α, and calls with a
queen α + 1/3 of the time. The game is worth -1/18 to the first player.
5000 iterations of CFR+ lands on α ≈ 0.222:

```
  J:                   pass 0.778         bet 0.222
  Q:                   pass 1.000         bet 0.000
  K:                   pass 0.333         bet 0.667
  Q:pb                 pass 0.444         bet 0.556
  J:p                  pass 0.667         bet 0.333    <- second player bluffs a third of the time
```

with EV -0.05556. Leduc with DCFR (an actual run, ~1.4s on my laptop):

```
leduc: 288 infosets, 774 decision nodes, 1116 terminals
   iter   secs    ev(p0)  exploit (mbb/g)
    100    0.1  -0.08583            7.755
    200    0.3  -0.08564            2.552
    300    0.4  -0.08562            1.247
    400    0.5  -0.08561            0.711
    500    0.7  -0.08561            0.425
    600    0.8  -0.08561            0.389
    700    1.0  -0.08561            0.265
    800    1.1  -0.08561            0.243
    900    1.2  -0.08561            0.249
   1000    1.4  -0.08561            0.183

  J:             check/call 0.927   bet/raise 0.073
  Q:             check/call 0.258   bet/raise 0.742
  K:             check/call 0.246   bet/raise 0.754
  J:c            check/call 0.701   bet/raise 0.299
  Q:c            check/call 0.150   bet/raise 0.850
  K:c            check/call 0.000   bet/raise 1.000
  J:r                  fold 0.819  check/call 0.126   bet/raise 0.055
  Q:r                  fold 0.000  check/call 0.629   bet/raise 0.371
  K:r                  fold 0.000  check/call 0.418   bet/raise 0.582
  J:cr                 fold 0.946  check/call 0.035   bet/raise 0.019
  Q:cr                 fold 0.000  check/call 0.843   bet/raise 0.157
  K:cr                 fold 0.000  check/call 0.304   bet/raise 0.696
  J:rr                 fold 0.000  check/call 1.000
  Q:rr                 fold 0.000  check/call 1.000
  K:rr                 fold 0.000  check/call 1.000
  J:crr                fold 0.000  check/call 1.000
  Q:crr                fold 0.000  check/call 1.000
```

The value settles at -0.0856, which matches the published value of Leduc.
Exploitability is in milli-chips per hand; uniform random play is ~2374.

Fun things the bot figured out on its own: it slow-plays kings preflop a
quarter of the time, bluff-bets jacks ~30% of the time when checked to,
and never folds once there have been two raises - the pot odds are too good.

### cfr vs cfr+ vs dcfr

```
exploitability in mbb/g on leduc
  iter        cfr       cfr+       dcfr
     1   2373.611   2373.611   2373.611
     2   2061.319   2057.917   2055.194
     4   1659.026   1609.655   1654.766
     7   1156.581   1011.154   1175.327
    13    707.272    409.925    383.346
    24    405.673    130.791    111.049
    45    215.657     40.288     26.416
    84    115.038     17.540     11.011
   159     61.399      6.882      3.114
   299     35.488      2.327      1.216
   563     18.936      0.726      0.333
  1062     11.409      0.226      0.150
  2000      6.918      0.077      0.038
  secs        2.5        2.6        2.6

 2373.61 |*    *    *   *                                         
         |              +   o                                     
         |                  *   o    o                            
  186.22 |                      *         o                       
         |                           +        o    o              
         |                           *    +            o          
   14.61 |                                *   +             o    o
         |                                    *                   
         |                                         *              
    1.15 |                                             +          
         |                                             *    +     
         |                                                  *     
    0.09 |                                                       +
```

Vanilla CFR is still at ~7 mbb/g after 2000 iterations; CFR+ and DCFR pass
that before iteration 160 and keep going. DCFR is the fastest early on
because it forgets the junk from the first few iterations quickly.

## a bug worth writing down

My first version skipped opponent actions with zero probability during the
traversal ("they contribute nothing, why recurse?"). The EV still looked
fine, but at 300 iterations on Leduc exploitability was 2.5x worse for CFR+, 6x for CFR and ~100x for DCFR. The
skipped subtrees contain *my own* infosets, and their average strategy is
weighted by my reach, not the opponent's - so they silently missed updates.
Exploitability is the only metric that caught it. That's also why the
tests check it rather than just the game value.

## what I'd do next

- Monte Carlo CFR (external/outcome sampling) so it scales past toy games
- vectorise over private hands on the public tree, which is how real solvers do it
- abstraction + a depth-limited re-solve to try a tiny no-limit variant
- a proper GUI table instead of the text prompts

## license

MIT
