"""Offline behavioural test for the distinct-pour guard in game.py.

Run:  python3 hub/test_distinct_pour.py     (exit 0 = all pass)

Bug it locks down (seen live 2026-09-04): person A withdraws a sub-threshold
amount (no glass), person B withdraws a full glass moments later, and B's count
jumps by 2 because A's leftover partial was merged into B's pour. A glass must
only ever be credited to the person who physically withdrew it.
"""
import sys, tempfile, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
config.RESUME_SESSION = False          # force a fresh session each Game()
from storage import Storage
from game import Game


def fresh_game():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(path)
    g = Game(Storage(path))
    g.start(node_count=2)
    return g


def active(g, node):
    g.on_pour_active({"msg": "POUR_ACTIVE", "node": node, "delta_g": 5.0})


_seq = [0]
def settle(g, node, grams):
    _seq[0] += 1
    g.on_pour_settled({"msg": "POUR_SETTLED", "node": node, "delta_g": float(grams),
                       "sigma_g": 6.0, "seq": _seq[0]})


def gc(g, node):
    return g.get_state()["glass_count"][node]


def main():
    fails = 0

    # 1 — THE BUG: A 95g (no glass), then B 105g within the window. B gets 1, not 2.
    g = fresh_game()
    active(g, 0); settle(g, 0, 95)
    active(g, 0); settle(g, 0, 105)
    got = gc(g, 0); ok = got == 1
    print(f"[1] cross-person no-merge:      count={got} expect=1  {'PASS' if ok else 'FAIL'}")
    fails += not ok

    # 2 — split-settle of ONE pour (no POUR_ACTIVE between fragments): 90 + 60 = 1 glass
    g = fresh_game()
    active(g, 0); settle(g, 0, 90)
    settle(g, 0, 60)
    got = gc(g, 0); ok = got == 1
    print(f"[2] split-settle still merges:  count={got} expect=1  {'PASS' if ok else 'FAIL'}")
    fails += not ok

    # 3 — four consecutive real glasses, each its own pour
    g = fresh_game()
    for _ in range(4):
        active(g, 1); settle(g, 1, 140)
    got = gc(g, 1); ok = got == 4
    print(f"[3] 4 consecutive glasses:      count={got} expect=4  {'PASS' if ok else 'FAIL'}")
    fails += not ok

    # 4 — one continuous big pour = 2 glasses
    g = fresh_game()
    active(g, 0); settle(g, 0, 250)
    got = gc(g, 0); ok = got == 2
    print(f"[4] single 250g pour:           count={got} expect=2  {'PASS' if ok else 'FAIL'}")
    fails += not ok

    # 5 — two sub-threshold DISTINCT pours must not manufacture a phantom glass
    g = fresh_game()
    active(g, 1); settle(g, 1, 95)
    active(g, 1); settle(g, 1, 95)
    got = gc(g, 1); ok = got == 0
    print(f"[5] two small distinct pours:   count={got} expect=0  {'PASS' if ok else 'FAIL'}")
    fails += not ok

    print("\n" + ("ALL PASS" if fails == 0 else f"{fails} FAIL(S)"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
