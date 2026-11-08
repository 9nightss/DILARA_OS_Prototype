#!/usr/bin/env python3
"""Summarise playtest_log.csv from tron_lightcycle.py, one row per enemy
behaviour (voronoi / rinzler / clu / random).

    python analyze_playtest.py                          # playtest_log.csv next to this file
    python analyze_playtest.py a.csv b.csv              # merge logs from several testers
    python analyze_playtest.py --teams solo --enemies 3 # only that arena setup

Only rounds with a single human are analysed (two-human rounds are ignored).
Testers can change the number of enemies and switch to team play, so rounds from
different setups are NOT comparable - filter with --teams / --enemies (and
--allies) for a clean comparison. Logs written before those options existed are
read as solo play against 3 enemies. No third-party packages needed.
"""
import argparse
import csv
import os
import random
import statistics as st
import sys
from collections import Counter, defaultdict

MIN_ROUNDS = 20          # per condition, before any comparison is worth reading
PERMUTATIONS = 5000


def load(paths):
    rows = []
    for path in paths:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("mode") != "solo":          # solo = one human
                    continue
                try:
                    r["p1_survival_s"] = float(r["p1_survival_s"])
                    r["enemies_dead"] = int(r["enemies_dead"])
                    r["first_enemy_death_s"] = float(r["first_enemy_death_s"]) if r["first_enemy_death_s"] else None
                except (ValueError, KeyError):
                    continue
                # columns added later: old logs were always solo play vs 3 enemies
                r["teams"] = r.get("teams") or "solo"
                r["enemies"] = int(r.get("enemies") or 3)
                r["allies"] = int(r.get("allies") or 0)
                rows.append(r)
    return rows


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "    - "


def perm_pvalue(a, b, stat=st.mean, n=PERMUTATIONS, seed=1):
    """Two-sided permutation test on the difference of `stat` between samples."""
    if len(a) < 2 or len(b) < 2:
        return None
    rng = random.Random(seed)
    observed = abs(stat(a) - stat(b))
    pool = list(a) + list(b)
    hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        if abs(stat(pool[:len(a)]) - stat(pool[len(a):])) >= observed:
            hits += 1
    return (hits + 1) / (n + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="log file(s); default: playtest_log.csv next to this script")
    ap.add_argument("--teams", choices=["solo", "team"], help="only free-for-all or only team rounds")
    ap.add_argument("--enemies", type=int, help="only rounds with this many enemies")
    ap.add_argument("--allies", type=int, help="only rounds with this many allies")
    args = ap.parse_args()

    paths = args.paths or [os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest_log.csv")]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit(f"not found: {', '.join(missing)}")
    rows = load(paths)
    if not rows:
        sys.exit("no single-human rounds in the log yet")

    configs = Counter((r["teams"], r["enemies"], r["allies"]) for r in rows)
    if args.teams:
        rows = [r for r in rows if r["teams"] == args.teams]
    if args.enemies is not None:
        rows = [r for r in rows if r["enemies"] == args.enemies]
    if args.allies is not None:
        rows = [r for r in rows if r["allies"] == args.allies]
    if not rows:
        sys.exit("no rounds match that filter. Setups in the log (teams, enemies, allies): "
                 + ", ".join(f"{k}x{v}" for k, v in sorted(configs.items())))

    shown = Counter((r["teams"], r["enemies"], r["allies"]) for r in rows)
    sessions = len({r["session"] for r in rows})
    print(f"{len(rows)} rounds from {sessions} session(s)")
    print("setups (mode, enemies, allies): " + ", ".join(f"{k[0]}/{k[1]}/{k[2]} x{v}" for k, v in sorted(shown.items())))
    if len(shown) > 1:
        print("! rounds from different setups are mixed - use --teams / --enemies / --allies for a clean comparison.")
    print()

    by_cond = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)
    conds = sorted(by_cond)

    print(f"{'condition':<9} {'rounds':>6} {'win':>7} {'loss':>7} {'draw':>7} "
          f"{'survive s (median)':>19} {'survive s, losses':>18} {'enemies dead':>13} {'1st enemy dies s':>17}")
    for c in conds:
        rs = by_cond[c]
        n = len(rs)
        outc = Counter(r["outcome"] for r in rs)
        surv = [r["p1_survival_s"] for r in rs]
        surv_loss = [r["p1_survival_s"] for r in rs if r["outcome"] == "LOSS"]
        first = [r["first_enemy_death_s"] for r in rs if r["first_enemy_death_s"] is not None]
        print(f"{c:<9} {n:>6} {pct(outc['WIN'], n):>7} {pct(outc['LOSS'], n):>7} {pct(outc['DRAW'], n):>7} "
              f"{st.median(surv):>19.1f} {(st.median(surv_loss) if surv_loss else float('nan')):>18.1f} "
              f"{st.mean(r['enemies_dead'] for r in rs):>13.2f} "
              f"{(st.median(first) if first else float('nan')):>17.1f}")

    print("\nHow the human died (losses only; 'enemy' = ran into another cycle's trail or head):")
    for c in conds:
        losses = [r for r in by_cond[c] if r["outcome"] == "LOSS"]
        causes = Counter(r["p1_death_cause"] or "?" for r in losses)
        total = len(losses)
        parts = "  ".join(f"{k} {pct(v, total).strip()}" for k, v in causes.most_common())
        print(f"  {c:<9} ({total} losses)  {parts}")

    print("\nPairwise comparisons (permutation test):")
    thin = [c for c in conds if len(by_cond[c]) < MIN_ROUNDS]
    for i, a in enumerate(conds):
        for b in conds[i + 1:]:
            ra, rb = by_cond[a], by_cond[b]
            win_a = [1.0 if r["outcome"] == "WIN" else 0.0 for r in ra]
            win_b = [1.0 if r["outcome"] == "WIN" else 0.0 for r in rb]
            p_win = perm_pvalue(win_a, win_b)
            la = [r["p1_survival_s"] for r in ra if r["outcome"] == "LOSS"]
            lb = [r["p1_survival_s"] for r in rb if r["outcome"] == "LOSS"]
            p_surv = perm_pvalue(la, lb, stat=st.median)

            def fmt(p):
                return "n/a" if p is None else f"p={p:.3f}"
            print(f"  {a} vs {b}:  win rate {fmt(p_win)}   survival time in losses (median) {fmt(p_surv)}")

    print()
    if thin:
        print(f"! Fewer than {MIN_ROUNDS} rounds for: {', '.join(thin)} - treat every number above as anecdotal.")
    print("Notes: survival time is the round length when the human dies. A quick WIN is also a short round, so read")
    print("survival from the 'losses' column and the win rate together. The in-game score (seconds x 100) mixes")
    print("both and is not a clean measure of enemy difficulty. This log records behaviour, not opinions - how the")
    print("bots *felt* needs a separate rating question.")


if __name__ == "__main__":
    main()