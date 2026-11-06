#!/usr/bin/env python3
"""Build a PowerPoint report from the Daily 539 3-month analysis."""

import csv
import json
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

FONT = "Microsoft JhengHei"

DARK = RGBColor(0x0F, 0x2B, 0x46)
NAVY = RGBColor(0x16, 0x3A, 0x5F)
RED = RGBColor(0xE6, 0x39, 0x46)
ORANGE = RGBColor(0xF4, 0xA2, 0x61)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
BLUE = RGBColor(0x45, 0x7B, 0x9D)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x6B, 0x72, 0x80)
MID = RGBColor(0x94, 0xA3, 0xB8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SW, SH = 13.333, 7.5


def load_data(csv_path, json_path):
    analysis = json.loads(Path(json_path).read_text(encoding="utf-8"))
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    lo, hi = analysis["window"]["from"], analysis["window"]["to"]
    window = [r for r in rows if lo <= r["lotteryDate"] <= hi]
    draws = [[int(r[k]) for k in ("n1", "n2", "n3", "n4", "n5")] for r in window]
    sums = [sum(d) for d in draws]
    odd = Counter(sum(1 for n in d if n % 2) for d in draws)
    return analysis, sums, odd


def add_bg(slide, color):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(SW), Inches(SH))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    bg.shadow.inherit = False
    return bg


def add_rect(slide, left, top, width, height, color, shape=MSO_SHAPE.RECTANGLE):
    box = slide.shapes.add_shape(shape, Inches(left), Inches(top), Inches(width), Inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = color
    box.line.fill.background()
    box.shadow.inherit = False
    return box


def add_text(slide, text, left, top, width, height, size=16, bold=False,
             color=DARK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.1):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        run = p.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return box


def add_ball(slide, number, left, top, diameter=0.62, fill=RED, text_color=WHITE, size=18):
    ball = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left), Inches(top),
                                  Inches(diameter), Inches(diameter))
    ball.fill.solid()
    ball.fill.fore_color.rgb = fill
    ball.line.fill.background()
    ball.shadow.inherit = False
    tf = ball.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = f"{number:02d}"
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.color.rgb = text_color
    return ball


def add_header(slide, title, subtitle=None, page=None):
    add_bg(slide, LIGHT)
    add_rect(slide, 0, 0, SW, 0.13, DARK)
    add_rect(slide, 0.7, 0.55, 0.12, 0.62, RED)
    add_text(slide, title, 0.95, 0.5, 9.5, 0.75, size=30, bold=True, color=DARK,
             anchor=MSO_ANCHOR.MIDDLE)
    if subtitle:
        add_text(slide, subtitle, 0.97, 1.24, 11.4, 0.4, size=13, color=GRAY)
    if page is not None:
        add_text(slide, f"{page:02d}", 12.2, 6.95, 0.6, 0.3, size=11, color=MID,
                 align=PP_ALIGN.RIGHT)


def style_chart(chart, title, color=TEAL, data_labels=True):
    chart.has_title = True
    chart.chart_title.text_frame.text = title
    for p in chart.chart_title.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = FONT
            r.font.size = Pt(14)
            r.font.bold = True
            r.font.color.rgb = DARK
    chart.has_legend = False
    chart.font.name = FONT
    chart.font.size = Pt(11)
    chart.font.color.rgb = GRAY
    plot = chart.plots[0]
    plot.gap_width = 55
    if data_labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.font.name = FONT
        dl.font.size = Pt(10)
        dl.font.color.rgb = DARK
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = color
    series.format.line.fill.background()
    chart.category_axis.tick_labels.font.name = FONT
    chart.category_axis.tick_labels.font.size = Pt(10)
    chart.category_axis.tick_labels.font.color.rgb = DARK
    chart.category_axis.format.line.color.rgb = MID
    chart.value_axis.tick_labels.font.name = FONT
    chart.value_axis.tick_labels.font.size = Pt(9)
    chart.value_axis.tick_labels.font.color.rgb = GRAY
    chart.value_axis.has_major_gridlines = True
    chart.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
    chart.value_axis.format.line.fill.background()
    return chart


def build(analysis, sums, odd_counts, out_path):
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    blank = prs.slide_layouts[6]

    latest = analysis["latestDraw"]
    freq = analysis["frequency"]
    overall = analysis["overall"]
    picks = analysis["statisticalPicks"]

    # ---------- 1. Cover ----------
    s = prs.slides.add_slide(blank)
    add_bg(s, DARK)
    add_rect(s, 0, 0, 0.22, SH, RED)
    add_rect(s, 8.9, 0, 4.44, SH, NAVY)
    for i, (num, color) in enumerate([(30, RED), (23, TEAL), (19, ORANGE), (7, BLUE), (2, MID)]):
        add_ball(s, num, 9.35 + (i % 3) * 1.22, 2.35 + (i // 3) * 1.32, 1.0, color, size=26)
    add_text(s, "TAIWAN LOTTERY  ·  DAILY 539", 0.9, 1.15, 7.5, 0.4, size=13, bold=True, color=ORANGE)
    add_text(s, "今彩539", 0.9, 1.75, 7.6, 0.95, size=54, bold=True, color=WHITE)
    add_text(s, "三個月開獎數據分析", 0.9, 2.72, 7.8, 0.8, size=38, bold=True, color=WHITE)
    add_text(s, "與統計推測", 0.9, 3.5, 7.8, 0.7, size=38, bold=True, color=WHITE)
    add_rect(s, 0.92, 4.5, 1.6, 0.06, RED)
    add_text(s, f"{analysis['window']['from']}  —  {analysis['window']['to']}", 0.9, 4.78, 7.0, 0.45,
             size=18, color=RGBColor(0xC9, 0xD6, 0xE3))
    add_text(s, f"共 {analysis['window']['draws']} 期開獎資料　·　最新期別 {latest['period']}", 0.9, 5.25, 7.5, 0.4,
             size=14, color=MID)
    add_text(s, "※ 彩券每期獨立隨機，本簡報之推測僅為歷史統計整理，非中獎保證。", 0.9, 6.55, 11.6, 0.4,
             size=11, color=MID)

    # ---------- 2. Summary ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "分析摘要", "近三個月開獎資料總覽與最新一期結果", page=2)
    cards = [
        (f"{analysis['window']['draws']}", "分析期數", "2026/08/01 – 2026/10/26", TEAL),
        (f"{latest['period']}", "最新期別", f"{latest['date']} 開獎", RED),
        (f"{overall['sumAvg']}", "和值平均", f"標準差 {overall['sumStd']}", ORANGE),
        (f"{overall['odd']}:{overall['even']}", "奇偶比", f"奇數 {overall['oddPct']}%", BLUE),
    ]
    for i, (big, label, note, color) in enumerate(cards):
        left = 0.7 + i * 3.08
        add_rect(s, left, 1.95, 2.86, 2.05, CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_rect(s, left, 1.95, 0.1, 2.05, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(s, label, left + 0.3, 2.18, 2.3, 0.3, size=13, bold=True, color=GRAY)
        add_text(s, big, left + 0.28, 2.55, 2.4, 0.75, size=32, bold=True, color=color)
        add_text(s, note, left + 0.3, 3.38, 2.35, 0.35, size=10, color=MID)

    add_rect(s, 0.7, 4.35, 11.93, 2.2, CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(s, "最新一期開獎號碼", 1.0, 4.58, 4.0, 0.4, size=15, bold=True, color=DARK)
    add_text(s, f"{latest['date']}　第 {latest['period']} 期", 1.0, 4.98, 4.6, 0.35, size=11, color=GRAY)
    for i, n in enumerate(latest["numbers"]):
        add_ball(s, n, 5.05 + i * 0.95, 4.85, 0.78, RED if i == 0 else NAVY, size=22)
    add_text(s, "號碼由小到大顯示", 10.25, 5.05, 2.1, 0.35, size=10, color=MID, align=PP_ALIGN.RIGHT)
    zones = overall["zones"]
    add_text(s, f"區間分布　1–13：{zones.get('1-13', 0)} 顆　·　14–26：{zones.get('14-26', 0)} 顆　·　27–39：{zones.get('27-39', 0)} 顆",
             1.0, 6.0, 10.8, 0.35, size=11, color=GRAY)

    # ---------- 3. Hot / cold / overdue ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "熱門、冷門與久未開出號碼", "以 74 期出現次數與遺漏期數整理", page=3)
    panels = [
        ("熱門號碼 TOP 8", analysis["hotNumbers"], TEAL, "出現次數最多"),
        ("冷門號碼 BOTTOM 5", analysis["coldNumbers"], BLUE, "出現次數最少"),
        ("久未開出 TOP 8", analysis["mostOverdue"], RED, "距離最近一次開出最久"),
    ]
    freq_map = {r["number"]: r for r in freq}
    for i, (title, numbers, color, note) in enumerate(panels):
        left = 0.7 + i * 4.05
        add_rect(s, left, 1.85, 3.75, 4.95, CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_rect(s, left, 1.85, 3.75, 0.78, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(s, title, left + 0.25, 1.98, 3.3, 0.35, size=14, bold=True, color=WHITE)
        add_text(s, note, left + 0.25, 2.3, 3.3, 0.28, size=10, color=WHITE)
        cols = 4 if len(numbers) > 5 else 3
        for j, n in enumerate(numbers):
            col, row = j % cols, j // cols
            add_ball(s, n, left + 0.42 + col * 0.85, 2.95 + row * 0.95, 0.66, color, size=19)
            info = freq_map[n]
            if title.startswith("久未"):
                detail = f"{info['overdue']} 期未開"
            else:
                detail = f"{info['count']} 次"
            add_text(s, detail, left + 0.42 + col * 0.85 - 0.06, 3.6 + row * 0.95, 0.8, 0.25,
                     size=8, color=GRAY, align=PP_ALIGN.CENTER)
    add_text(s, "註：遺漏期數以最新一期往回計算；歷史頻率不代表下一期機率。", 0.75, 6.95, 11.8, 0.3,
             size=9, color=MID)

    # ---------- 4. Frequency chart ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "號碼出現次數（近 15 名）", "74 期共開出 370 顆號碼，平均每號約 9.5 次", page=4)
    top = freq[:15]
    top3 = {r["number"] for r in top[:3]}
    top_sorted = sorted(top, key=lambda r: r["number"])
    cd = CategoryChartData()
    cd.categories = [f"{r['number']:02d}" for r in top_sorted]
    cd.add_series("出現次數", [r["count"] for r in top_sorted])
    chart = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(1.75),
                               Inches(9.0), Inches(5.1), cd).chart
    style_chart(chart, "各號碼出現次數", TEAL)
    chart.value_axis.maximum_scale = 18
    chart.value_axis.minimum_scale = 0
    for idx, r in enumerate(top_sorted):
        pt = chart.plots[0].series[0].points[idx]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = RED if r["number"] in top3 else TEAL
    add_rect(s, 9.95, 1.85, 2.7, 2.3, CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(s, "最高出現", 10.2, 2.05, 2.2, 0.3, size=12, bold=True, color=GRAY)
    add_ball(s, top[0]["number"], 10.2, 2.45, 0.85, RED, size=24)
    add_text(s, f"{top[0]['count']} 次", 11.2, 2.55, 1.3, 0.5, size=24, bold=True, color=RED)
    add_text(s, f"出現率 {top[0]['pct']}%", 11.2, 3.05, 1.3, 0.3, size=10, color=GRAY)
    add_text(s, "紅色柱為出現次數前三名；其餘為藍綠色。", 10.0, 4.4, 2.6, 0.8, size=10, color=GRAY)
    add_text(s, f"出現最少：{freq[-1]['number']:02d}（{freq[-1]['count']} 次）　久未開出：{freq_map[analysis['mostOverdue'][0]]['number']:02d}（{freq_map[analysis['mostOverdue'][0]]['overdue']} 期）",
             10.0, 5.3, 2.65, 0.9, size=10, color=GRAY)

    # ---------- 5. Sum & odd distribution ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "和值與奇偶分布", "檢視開獎組合是否接近隨機均衡", page=5)
    bins = [(50, 69), (70, 89), (90, 109), (110, 129), (130, 149), (150, 169)]
    bin_counts = [sum(1 for v in sums if lo <= v <= hi) for lo, hi in bins]
    cd = CategoryChartData()
    cd.categories = [f"{lo}–{hi}" for lo, hi in bins]
    cd.add_series("期數", bin_counts)
    chart = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(1.8),
                               Inches(6.0), Inches(4.9), cd).chart
    style_chart(chart, "五個號碼和值分布", BLUE)
    chart.value_axis.maximum_scale = max(bin_counts) + 5

    cd2 = CategoryChartData()
    cd2.categories = [f"{k} 個奇數" for k in range(6)]
    cd2.add_series("期數", [odd_counts.get(k, 0) for k in range(6)])
    chart2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.0), Inches(1.8),
                                Inches(5.6), Inches(4.9), cd2).chart
    style_chart(chart2, "每期奇數個數分布", ORANGE)
    chart2.value_axis.maximum_scale = max(odd_counts.values()) + 5
    for idx in (2, 3):
        pt = chart2.plots[0].series[0].points[idx]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = ORANGE
    for idx in (0, 1, 4, 5):
        pt = chart2.plots[0].series[0].points[idx]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = RGBColor(0xC9, 0xD3, 0xDF)

    add_text(s, f"平均和值 {overall['sumAvg']}（標準差 {overall['sumStd']}，實際範圍 {overall['sumMin']}–{overall['sumMax']}）；奇偶累計 {overall['odd']}:{overall['even']}，接近 1:1。",
             0.75, 6.8, 11.8, 0.35, size=10, color=GRAY)

    # ---------- 6. Statistical picks ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "下一次開獎統計推測", "以熱門度＋遺漏期數加權，兼顧和值與奇偶平衡", page=6)
    add_rect(s, 0.7, 1.8, 11.93, 0.62, NAVY, MSO_SHAPE.ROUNDED_RECTANGLE)
    headers = [("組別", 1.05), ("推測號碼（5 個）", 2.2), ("和值", 10.35), ("奇 / 偶", 11.25)]
    for text, left in headers:
        add_text(s, text, left, 1.92, 1.4 if text != "推測號碼（5 個）" else 7.8, 0.35,
                 size=11, bold=True, color=WHITE)
    for i, p in enumerate(picks):
        top = 2.55 + i * 0.85
        add_rect(s, 0.7, top, 11.93, 0.75, CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(s, f"{i + 1}", 1.1, top + 0.17, 0.6, 0.4, size=18, bold=True,
                 color=RED if i == 0 else NAVY)
        for j, n in enumerate(p["numbers"]):
            add_ball(s, n, 2.15 + j * 0.76, top + 0.08, 0.58, RED if i == 0 else NAVY, size=16)
        add_text(s, str(p["sum"]), 10.35, top + 0.18, 0.8, 0.4, size=17, bold=True, color=DARK)
        add_text(s, f"{p['odd']} / {5 - p['odd']}", 11.2, top + 0.2, 1.0, 0.35, size=14, color=GRAY)
    add_rect(s, 0.7, 6.82, 0.1, 0.32, RED)
    add_text(s, "規則：60% 出現頻率 + 40% 遺漏期數；和值限制在平均 ±26；每組奇數 2–3 個；各組重複號碼不超過 2 個。",
             0.95, 6.83, 11.6, 0.35, size=10, color=GRAY)

    # ---------- 7. Conclusion ----------
    s = prs.slides.add_slide(blank)
    add_bg(s, DARK)
    add_rect(s, 0, 0, 0.22, SH, RED)
    add_text(s, "結論與提醒", 0.95, 0.85, 8.0, 0.7, size=34, bold=True, color=WHITE)
    add_rect(s, 0.97, 1.65, 1.5, 0.06, RED)
    points = [
        ("資料完整", f"近三個月共 {analysis['window']['draws']} 期，號碼、和值與奇偶分布皆接近隨機均衡。"),
        ("熱門與遺漏", "30、23、19 出現最多次；37、29、33 距離上次開出最久。"),
        ("統計推測", "以頻率、遺漏、和值與奇偶平衡產生 5 組參考組合，非實際預測。"),
        ("理性看待", "每期開獎為獨立事件，過去結果不改變下一期各號碼的中獎機率。"),
    ]
    for i, (head, body) in enumerate(points):
        top = 2.0 + i * 1.08
        add_ball(s, i + 1, 1.0, top + 0.04, 0.5, RED if i == 0 else NAVY, size=15)
        add_text(s, head, 1.75, top, 3.0, 0.38, size=16, bold=True, color=ORANGE)
        add_text(s, body, 1.75, top + 0.38, 10.6, 0.4, size=12,
                 color=RGBColor(0xC9, 0xD6, 0xE3))
    add_rect(s, 0.95, 6.45, 11.45, 0.68, RGBColor(0x24, 0x45, 0x68), MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(s, "本簡報僅供數據分析與娛樂參考，請量力而為、理性投注；實際開獎結果以台灣彩券官方公告為準。",
             1.2, 6.6, 11.0, 0.4, size=11, color=WHITE, align=PP_ALIGN.CENTER)

    prs.save(out_path)
    return len(prs.slides)


def main():
    analysis, sums, odd_counts = load_data("539_numbers.csv", "539_analysis_3m.json")
    out = Path("539_analysis.pptx")
    slides = build(analysis, sums, odd_counts, out)
    print(f"已產生 {out.name}（{slides} 頁，{out.stat().st_size} bytes）")


if __name__ == "__main__":
    main()
