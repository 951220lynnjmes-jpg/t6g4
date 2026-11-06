#!/usr/bin/env python3
"""Scrape Taiwan Lottery Daily 539 (今彩539) results from the official API."""

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

API = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) taiwan-539-scraper/1.0",
    "Accept": "application/json",
}
FIELDS = [
    "period", "lotteryDate", "sellAmount", "totalAmount",
    "n1", "n2", "n3", "n4", "n5",
    "drawOrder",
    "jackpotWinners", "jackpotPrize",
    "secondWinners", "secondPrize",
    "thirdWinners", "thirdPrize",
    "fourthWinners", "fourthPrize",
]


def fetch_page(month, end_month, page_num, page_size):
    query = urllib.parse.urlencode({
        "period": "",
        "month": month,
        "endMonth": end_month,
        "pageNum": page_num,
        "pageSize": page_size,
    })
    req = urllib.request.Request(f"{API}?{query}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("rtCode") != 0:
        raise RuntimeError(f"API error: {payload.get('rtMsg')}")
    return payload["content"] or {}


def fetch_range(month, end_month):
    rows, page_num, page_size = [], 1, 50
    while True:
        content = fetch_page(month, end_month, page_num, page_size)
        batch = content.get("daily539Res") or []
        if not batch:
            break
        rows.extend(batch)
        if len(rows) >= content.get("totalSize", 0):
            break
        page_num += 1
    return rows


def to_row(item):
    nums = item.get("drawNumberSize") or []
    date_str = (item.get("lotteryDate") or "")[:10]
    def winner(key):
        return (item.get(key) or {}).get("winnerCount", "")
    def prize(key):
        return (item.get(key) or {}).get("perPrize", "")
    return {
        "period": item.get("period"),
        "lotteryDate": date_str,
        "sellAmount": item.get("sellAmount"),
        "totalAmount": item.get("totalAmount"),
        "n1": nums[0] if len(nums) > 0 else "",
        "n2": nums[1] if len(nums) > 1 else "",
        "n3": nums[2] if len(nums) > 2 else "",
        "n4": nums[3] if len(nums) > 3 else "",
        "n5": nums[4] if len(nums) > 4 else "",
        "drawOrder": " ".join(f"{n:02d}" for n in (item.get("drawNumberAppear") or [])),
        "jackpotWinners": winner("d539JackpotAssign"),
        "jackpotPrize": prize("d539JackpotAssign"),
        "secondWinners": winner("d539SecondAssign"),
        "secondPrize": prize("d539SecondAssign"),
        "thirdWinners": winner("d539ThirdAssign"),
        "thirdPrize": prize("d539ThirdAssign"),
        "fourthWinners": winner("d539FourthAssign"),
        "fourthPrize": prize("d539FourthAssign"),
    }


def main():
    today = date.today()
    parser = argparse.ArgumentParser(description="Scrape Taiwan Lottery Daily 539 results.")
    parser.add_argument("--month", default=today.strftime("%Y-%m"),
                        help="Start month YYYY-MM (default: current month)")
    parser.add_argument("--end-month", default=None,
                        help="End month YYYY-MM (default: same as --month)")
    parser.add_argument("--out", default="539_numbers", help="Output file prefix")
    args = parser.parse_args()

    end_month = args.end_month or args.month
    items = fetch_range(args.month, end_month)
    rows = [to_row(i) for i in items]

    if not rows:
        print("No data returned for the requested period.", file=sys.stderr)
        return 1

    out = Path(args.out)
    out_json = out.with_suffix(".json")
    out_csv = out.with_suffix(".csv")
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    latest = rows[0]
    print(f"期別 {latest['period']}  {latest['lotteryDate']}")
    print("號碼（由小到大）：" + " ".join(f"{latest[k]:02d}" for k in ("n1", "n2", "n3", "n4", "n5")))
    print(f"開出順序：{latest['drawOrder']}")
    print(f"共 {len(rows)} 期 -> {out_csv.name}, {out_json.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
