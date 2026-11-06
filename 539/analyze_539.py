#!/usr/bin/env python3
"""Analyze the last three months of Taiwan Daily 539 draws and build statistical picks.

Lottery draws are independent random events. The "picks" below are a statistical
summary of past frequency/overdue patterns, not a real prediction of future draws.
"""

import argparse
import csv
import itertools
import json
from collections import Counter
from pathlib import Path

NUM_MIN, NUM_MAX = 1, 39


def load_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def draw_numbers(row):
    return [int(row[k]) for k in ("n1", "n2", "n3", "n4", "n5")]


def analyze(rows):
    rows = rows[:]  # newest first
    draws = [draw_numbers(r) for r in rows]
    total = len(draws)
    freq = Counter(n for d in draws for n in d)

    overdue = {}
    for n in range(NUM_MIN, NUM_MAX + 1):
        idx = next((i for i, d in enumerate(draws) if n in d), total)
        overdue[n] = idx

    rows_by_num = []
    max_freq = max(freq.values()) or 1
    max_overdue = max(overdue.values()) or 1
    for n in range(NUM_MIN, NUM_MAX + 1):
        f, o = freq.get(n, 0), overdue[n]
        score = 0.6 * (f / max_freq) + 0.4 * (o / max_overdue)
        rows_by_num.append({
            "number": n,
            "count": f,
            "pct": round(f / total * 100, 2),
            "overdue": o,
            "score": round(score, 4),
        })

    by_freq = sorted(rows_by_num, key=lambda x: (-x["count"], -x["overdue"], x["number"]))
    by_score = sorted(rows_by_num, key=lambda x: (-x["score"], -x["count"], x["number"]))

    odd_total = sum(1 for d in draws for n in d if n % 2)
    even_total = total * 5 - odd_total
    sums = [sum(d) for d in draws]
    sum_avg = sum(sums) / len(sums)
    sum_std = (sum((s - sum_avg) ** 2 for s in sums) / len(sums)) ** 0.5

    per_draw_odd = Counter(sum(1 for n in d if n % 2) for d in draws)
    zone_counter = Counter()
    for d in draws:
        for n in d:
            if n <= 13:
                zone_counter["1-13"] += 1
            elif n <= 26:
                zone_counter["14-26"] += 1
            else:
                zone_counter["27-39"] += 1

    return {
        "totalDraws": total,
        "dateRange": {"latest": rows[0]["lotteryDate"], "earliest": rows[-1]["lotteryDate"]},
        "latestDraw": {
            "period": rows[0]["period"],
            "date": rows[0]["lotteryDate"],
            "numbers": draws[0],
        },
        "frequency": by_freq,
        "hotNumbers": [r["number"] for r in by_freq[:8]],
        "coldNumbers": [r["number"] for r in by_freq[-5:]],
        "mostOverdue": [r["number"] for r in sorted(rows_by_num, key=lambda x: (-x["overdue"], x["number"]))[:8]],
        "ranking": by_score,
        "overall": {
            "odd": odd_total,
            "even": even_total,
            "oddPct": round(odd_total / (total * 5) * 100, 2),
            "sumMin": min(sums),
            "sumMax": max(sums),
            "sumAvg": round(sum_avg, 2),
            "sumStd": round(sum_std, 2),
            "oddPerDraw": {str(k): v for k, v in sorted(per_draw_odd.items())},
            "zones": dict(zone_counter),
        },
        "_sumAvg": sum_avg,
    }


def build_picks(analysis, count=5):
    ranking = analysis["ranking"]
    pool = [r["number"] for r in ranking[:18]]
    weight = {r["number"]: r["score"] for r in ranking}
    sum_avg = analysis["_sumAvg"]

    combos = []
    for combo in itertools.combinations(pool, 5):
        odd = sum(1 for n in combo if n % 2)
        if odd not in (2, 3):
            continue
        s = sum(combo)
        if not (sum_avg - 26 <= s <= sum_avg + 26):
            continue
        score = sum(weight[n] for n in combo)
        combos.append((score, combo, s))
    combos.sort(key=lambda x: (-x[0], x[1]))

    picks = []
    used_numbers = Counter()
    for score, combo, s in combos:
        if len(picks) >= count:
            break
        if any(used_numbers[n] >= 2 for n in combo):
            continue
        if any(len(set(combo) & set(p["numbers"])) > 2 for p in picks):
            continue
        used_numbers.update(combo)
        picks.append({
            "numbers": list(combo),
            "sum": s,
            "odd": sum(1 for n in combo if n % 2),
            "score": round(score, 4),
        })
    return picks


def main():
    parser = argparse.ArgumentParser(description="Analyze last 3 months of Daily 539 data.")
    parser.add_argument("--input", default="539_numbers.csv")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--out", default="539_analysis_3m")
    args = parser.parse_args()

    rows = load_rows(args.input)
    if not rows:
        raise SystemExit("No input rows found.")

    latest_month = rows[0]["lotteryDate"][:7]
    y, m = map(int, latest_month.split("-"))
    m -= args.months - 1
    while m <= 0:
        y, m = y - 1, m + 12
    lower = f"{y:04d}-{m:02d}-01"

    window = [r for r in rows if r["lotteryDate"] >= lower]
    window.sort(key=lambda r: r["lotteryDate"], reverse=True)

    analysis = analyze(window)
    picks = build_picks(analysis)

    result = {
        "window": {"from": window[-1]["lotteryDate"], "to": window[0]["lotteryDate"],
                   "draws": len(window)},
        "latestDraw": analysis["latestDraw"],
        "overall": analysis["overall"],
        "hotNumbers": analysis["hotNumbers"],
        "coldNumbers": analysis["coldNumbers"],
        "mostOverdue": analysis["mostOverdue"],
        "frequency": analysis["frequency"],
        "statisticalPicks": picks,
        "disclaimer": "彩券每期獨立隨機，歷史統計無法預測未來，以下僅供參考、非中獎保證。",
    }

    out = Path(args.out)
    out.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with out.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["number", "count", "pct", "overdue", "score"])
        for r in analysis["frequency"]:
            writer.writerow([f"{r['number']:02d}", r["count"], r["pct"], r["overdue"], r["score"]])

    print(f"分析區間：{window[-1]['lotteryDate']} ~ {window[0]['lotteryDate']}（{len(window)} 期）")
    print(f"最新一期：{analysis['latestDraw']['period']} {analysis['latestDraw']['date']} "
          + " ".join(f"{n:02d}" for n in analysis['latestDraw']['numbers']))
    print("熱門號碼：" + " ".join(f"{n:02d}" for n in analysis["hotNumbers"]))
    print("冷門號碼：" + " ".join(f"{n:02d}" for n in analysis["coldNumbers"]))
    print("久未開出：" + " ".join(f"{n:02d}" for n in analysis["mostOverdue"]))
    print("和值平均 %.1f（區間 %d~%d） 奇偶 %s" % (
        analysis["overall"]["sumAvg"], analysis["overall"]["sumMin"],
        analysis["overall"]["sumMax"],
        f"{analysis['overall']['odd']}:{analysis['overall']['even']}"))
    print("統計推測號碼：")
    for i, p in enumerate(picks, 1):
        print(f"  {i}. " + " ".join(f"{n:02d}" for n in p["numbers"])
              + f"  (和值 {p['sum']}, 奇 {p['odd']} / 偶 {5 - p['odd']})")
    print(f"輸出：{out.with_suffix('.json').name}, {out.with_suffix('.csv').name}")


if __name__ == "__main__":
    main()
