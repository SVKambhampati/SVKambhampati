#!/usr/bin/env python3
"""Render the animated SVG cards for the GitHub profile README.

Usage:
  GITHUB_TOKEN=... python scripts/render_cards.py   # fetch fresh data, then render
  python scripts/render_cards.py                    # render from data/contributions.json
  STATIC=1 python scripts/render_cards.py           # render final frames (for screenshots)

Everything is plain SVG + CSS keyframes + SMIL, because GitHub shows README
images in a sandbox: no JavaScript, no external fonts, no network.
"""
import json
import os
import urllib.request
from collections import OrderedDict
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
CARDS = ROOT / "cards"
STATIC = os.environ.get("STATIC") == "1"

# ── Edit these to change what the profile says ──────────────────────────────
USER = "SVKambhampati"
NAME_FIRST = "Shreyas"
NAME_LAST = "Kambhampati"
TAGLINE = "I build software people actually open twice."
SUBLINE = "macOS apps · data toys · cloud platforms · security"
SITE = "svk-eta.vercel.app"
FEATURED = [
    # (repo, one-liner, language, accent)
    ("sleeve", "Now-playing album art as a live, low-power macOS desktop.", "Swift", "red"),
    ("filmprint", "What your Letterboxd history says about you.", "TypeScript", "blue"),
    ("sentimentsignal", "Stock sentiment intelligence platform.", "TypeScript", "yellow"),
    ("CloudDeploy", "One-command cloud deploys, minus the YAML maze.", "TypeScript", "blue"),
]
# ────────────────────────────────────────────────────────────────────────────

PAPER, INK, MUTED, LINE = "#faf7f0", "#1b1a17", "#6f6a60", "#e6e0d3"
ACCENT = {"blue": "#2f5bea", "red": "#e5484d", "yellow": "#f2a900"}
LANG_COLOR = {"Swift": "#f05138", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
              "Python": "#3572A5", "C#": "#178600", "HTML": "#e34c26"}

SERIF = "'Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# Shared keyframes. Base styles are the FINAL state; keyframes only describe
# the entrance, so reduced-motion / STATIC simply shows the finished card.
BASE_CSS = f"""
.serif{{font-family:{SERIF}}} .sans{{font-family:{SANS}}} .mono{{font-family:{MONO}}}
@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes pop{{0%{{opacity:0;transform:scale(.2)}}70%{{opacity:1;transform:scale(1.25)}}100%{{transform:scale(1)}}}}
@keyframes swing{{0%{{opacity:0;transform:translateY(60px) rotate(-6deg)}}65%{{opacity:1;transform:translateY(-6px) rotate(1.5deg)}}100%{{transform:none}}}}
@keyframes pulse{{0%{{transform:scale(1);opacity:.55}}100%{{transform:scale(3.2);opacity:0}}}}
@keyframes nudge{{0%,80%,100%{{transform:none}}90%{{transform:translateX(4px)}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.rise{{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}}
.fade{{animation:fade .6s ease-out both}}
.grow{{transform-box:fill-box;transform-origin:bottom;animation:grow .7s cubic-bezier(.2,.8,.2,1) both}}
.pop{{transform-box:fill-box;transform-origin:center;animation:pop .45s ease-out both}}
.swing{{transform-box:fill-box;transform-origin:center bottom;animation:swing 1s cubic-bezier(.2,.8,.2,1) both}}
.ring{{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}}
.nudge{{animation:nudge 3s ease-in-out infinite}}
.blink{{animation:blink 1.6s ease-in-out infinite}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
if STATIC:
    BASE_CSS += "*{animation:none!important}"


def svg(w, h, body, css="", title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>{BASE_CSS}{css}</style>{body}</svg>")


def card_bg(w, h, r=18):
    return (f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{r}" fill="{PAPER}" '
            f'stroke="{LINE}" stroke-width="1.5"/>')


def d(seconds):
    return f"animation-delay:{seconds:.2f}s"


def shine(gid, base, hi, dur=4, begin=1.6):
    """Gradient that sweeps across text. SMIL, because SVG has no background-clip:text."""
    anim = "" if STATIC else (
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="-1 0;-1 0;1.2 0" keyTimes="0;0.55;1" dur="{dur}s" begin="{begin}s" '
        f'repeatCount="indefinite"/>')
    return (f'<linearGradient id="{gid}" x1="0" x2="1" y1="0" y2="0">'
            f'<stop offset="0" stop-color="{base}"/><stop offset=".42" stop-color="{base}"/>'
            f'<stop offset=".5" stop-color="{hi}"/><stop offset=".58" stop-color="{base}"/>'
            f'<stop offset="1" stop-color="{base}"/>{anim}</linearGradient>')


def count_up(final, x, y, cls, style, start=0.9, frames=18, step=0.05):
    """Number that counts up from zero: N <text> frames toggled with SMIL <set>."""
    if STATIC or final <= 0:
        return f'<text x="{x}" y="{y}" class="{cls}" style="{style}">{final:,}</text>'
    out = []
    vals = sorted({round(final * (i / frames) ** 0.6) for i in range(frames + 1)})
    for i, v in enumerate(vals):
        t0 = start + i * step
        last = i == len(vals) - 1
        end = "" if last else f' end="{t0 + step:.2f}s"'
        fill = ' fill="freeze"' if last else ""
        out.append(
            f'<text x="{x}" y="{y}" class="{cls}" style="{style}" visibility="hidden">{v:,}'
            f'<set attributeName="visibility" to="visible" begin="{t0:.2f}s"{end}{fill}/></text>')
    return "".join(out)


# ── Data ────────────────────────────────────────────────────────────────────
QUERY = """query($login:String!){user(login:$login){contributionsCollection{
contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    DATA.write_text(json.dumps(payload))


def load():
    cal = json.loads(DATA.read_text())["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(date.fromisoformat(x["date"]), x["contributionCount"]) for x in w["contributionDays"]]
             for w in cal["weeks"]]
    days = [d_ for w in weeks for d_ in w]
    months = OrderedDict()
    for dt, c in days:
        months.setdefault((dt.year, dt.month), 0)
        months[(dt.year, dt.month)] += c
    months = list(months.items())[-12:]
    streak = best = 0
    for _, c in days:
        streak = streak + 1 if c else 0
        best = max(best, streak)
    busiest = max(days, key=lambda x: x[1])
    return dict(total=cal["totalContributions"], weeks=weeks, days=days, months=months,
                active=sum(1 for _, c in days if c), best_streak=best, busiest=busiest)


# ── Cards ───────────────────────────────────────────────────────────────────
def hero():
    w, h = 880, 260
    body = [card_bg(w, h),
            f'<defs>{shine("sh", INK, ACCENT["blue"])}</defs>',
            # status pill
            f'<g class="fade" style="{d(0.1)}"><rect x="48" y="40" width="190" height="28" rx="14" fill="#fff" stroke="{LINE}"/>'
            f'<circle cx="66" cy="54" r="4.5" fill="#2fb36b" class="blink"/>'
            f'<text x="80" y="58.5" class="mono" font-size="12" fill="{MUTED}">currently building</text></g>',
            f'<text x="48" y="128" class="serif rise" font-size="58" fill="{INK}" style="{d(0.25)}">{NAME_FIRST}</text>',
            f'<text x="48" y="186" class="serif rise" font-size="58" font-style="italic" fill="url(#sh)" style="{d(0.45)}">{NAME_LAST}</text>',
            f'<text x="48" y="226" class="sans rise" font-size="15" fill="{MUTED}" style="{d(0.7)}">{escape(TAGLINE)}</text>']
    # right column: a little "terminal" that types out what I'm into
    lines = [("$", "whoami"), (">", SUBLINE.split(" · ")[0]), (">", SUBLINE.split(" · ")[1]),
             (">", SUBLINE.split(" · ")[2]), (">", SUBLINE.split(" · ")[3]), ("$", "open " + SITE)]
    tx, ty = 540, 52
    body.append(f'<g class="fade" style="{d(0.5)}"><rect x="{tx}" y="{ty}" width="300" height="168" rx="12" fill="{INK}"/>'
                + "".join(f'<circle cx="{tx+18+i*14}" cy="{ty+16}" r="4" fill="{c}"/>'
                          for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])) + "</g>")
    for i, (p, t) in enumerate(lines):
        col = ACCENT["yellow"] if p == "$" else "#cfc8b8"
        body.append(f'<text x="{tx+18}" y="{ty+50+i*20}" class="mono fade" font-size="12.5" fill="{col}" '
                    f'style="{d(0.9+i*0.28)}"><tspan fill="#7d7768">{p} </tspan>{escape(t)}</text>')
    cy = ty + 50 + (len(lines) - 1) * 20
    body.append(f'<rect x="{tx+18+ (len(lines[-1][1])+2)*7.6:.0f}" y="{cy-11}" width="8" height="14" fill="{ACCENT["yellow"]}" '
                f'class="blink" style="{d(0.9+len(lines)*0.28)}"/>')
    return svg(w, h, "".join(body), title=f"{NAME_FIRST} {NAME_LAST} — {TAGLINE}")


def tile(label, value, foot, accent, delay, suffix=""):
    w, h = 286, 170
    col = ACCENT[accent]
    ink_on = INK if accent == "yellow" else "#fff"
    body = [f'<g class="swing" style="{d(delay)}">',
            f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="{col}"/>',
            f'<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".28"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="c"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18"/></clipPath></defs>',
            f'<circle cx="{w-30}" cy="30" r="6" fill="{ink_on}" opacity=".9"/>',
            f'<circle cx="{w-30}" cy="30" r="6" fill="none" stroke="{ink_on}" stroke-width="2" class="ring" style="{d(delay+1)}"/>',
            f'<text x="24" y="40" class="mono" font-size="12" letter-spacing="1.5" fill="{ink_on}" opacity=".85">{label.upper()}</text>',
            count_up(value, 24, 112, "serif", f"font-size:64px;fill:{ink_on}", start=delay + 0.6),
            f'<text x="24" y="146" class="sans" font-size="13.5" fill="{ink_on}" opacity=".9">{escape(foot)}</text>']
    if not STATIC:
        body.append(f'<rect x="-120" y="0" width="100" height="{h}" fill="url(#g)" clip-path="url(#c)" transform="skewX(-18)">'
                    f'<animate attributeName="x" values="-160;-160;{w+80}" keyTimes="0;.7;1" dur="5s" '
                    f'begin="{delay+1.4:.1f}s" repeatCount="indefinite"/></rect>')
    body.append("</g>")
    return svg(w, h, "".join(body), title=f"{label}: {value}{suffix}")


def activity(s):
    w, h = 880, 250
    months = s["months"]
    mx = max(c for _, c in months) or 1
    left, base, top = 48, 200, 78
    bw, gap = 46, (w - 2 * left - 12 * 46) / 11
    best_i = max(range(len(months)), key=lambda i: months[i][1])
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    body = [card_bg(w, h),
            f'<text x="48" y="48" class="serif rise" font-size="26" fill="{INK}">A year of commits</text>',
            f'<text x="{w-48}" y="48" text-anchor="end" class="mono fade" font-size="12" fill="{MUTED}" style="{d(0.3)}">'
            f'{s["total"]:,} contributions · last 12 months</text>',
            f'<line x1="{left}" x2="{w-left}" y1="{base}" y2="{base}" stroke="{LINE}"/>']
    for i, ((yr, mo), c) in enumerate(months):
        x = left + i * (bw + gap)
        bh = max(3, (base - top) * c / mx) if c else 3
        col = ACCENT["blue"] if i == best_i else ("#c9c1b1" if c else LINE)
        body.append(f'<rect x="{x:.1f}" y="{base-bh:.1f}" width="{bw}" height="{bh:.1f}" rx="6" fill="{col}" '
                    f'class="grow" style="{d(0.3+i*0.06)}"/>')
        body.append(f'<text x="{x+bw/2:.1f}" y="{base+22}" text-anchor="middle" class="mono" font-size="11" '
                    f'fill="{INK if i == best_i else MUTED}">{names[mo-1]}</text>')
        if i == best_i:
            body.append(f'<g class="pop" style="{d(1.3)}"><text x="{x+bw/2:.1f}" y="{base-bh-12:.1f}" text-anchor="middle" '
                        f'class="serif" font-size="20" fill="{ACCENT["blue"]}">{c}</text></g>')
    return svg(w, h, "".join(body), title=f"Monthly contributions, {s['total']} total")


def heatmap(s):
    weeks = s["weeks"][-53:]
    cell, g = 12, 3
    w, h = 880, 200
    ox = (w - len(weeks) * (cell + g) + g) / 2
    oy = 70
    mx = max(c for _, c in s["days"]) or 1
    shades = [LINE, "#c6d3fa", "#8ea7f3", "#5679ec", ACCENT["blue"]]

    def shade(c):
        if not c:
            return shades[0]
        return shades[min(4, 1 + int(3.999 * (c / mx) ** 0.5))]

    bd, bc = s["busiest"]
    body = [card_bg(w, h),
            f'<text x="48" y="44" class="serif rise" font-size="22" fill="{INK}">Contribution graph</text>',
            f'<text x="{w-48}" y="44" text-anchor="end" class="mono fade" font-size="12" fill="{MUTED}" style="{d(0.3)}">'
            f'longest streak {s["best_streak"]}d · busiest {bd:%b %-d} ({bc})</text>']
    for wi, wk in enumerate(weeks):
        for dt, c in wk:
            x = ox + wi * (cell + g)
            y = oy + dt.isoweekday() % 7 * (cell + g)
            body.append(f'<rect x="{x:.1f}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{shade(c)}" '
                        f'class="pop" style="{d(0.2+wi*0.025)}"/>')
    return svg(w, h, "".join(body), title=f"Contribution graph, {s['total']} contributions")


def repo_card(name, blurb, lang, accent, delay):
    w, h = 433, 120
    col = ACCENT[accent]
    body = [f'<g class="rise" style="{d(delay)}">', card_bg(w, h, 16),
            f'<clipPath id="rc"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16"/></clipPath>',
            f'<rect x="1" y="1" width="7" height="{h-2}" fill="{col}" clip-path="url(#rc)"/>',
            f'<text x="30" y="44" class="serif" font-size="24" fill="{INK}">{escape(name)}</text>',
            f'<g class="nudge"><text x="{w-30}" y="44" text-anchor="end" class="sans" font-size="20" fill="{col}">→</text></g>',
            f'<text x="30" y="72" class="sans" font-size="13.5" fill="{MUTED}">{escape(blurb)}</text>',
            f'<circle cx="36" cy="96" r="5" fill="{LANG_COLOR.get(lang, MUTED)}"/>',
            f'<text x="48" y="100" class="mono" font-size="11.5" fill="{MUTED}">{escape(lang)}</text></g>']
    return svg(w, h, "".join(body), title=f"{name}: {blurb}")


def main():
    fetch()
    s = load()
    CARDS.mkdir(exist_ok=True)
    out = {
        "hero.svg": hero(),
        "tile-total.svg": tile("contributions", s["total"], "in the last 12 months", "blue", 0.1),
        "tile-active.svg": tile("days shipping", s["active"], f"longest streak: {s['best_streak']} days", "red", 0.25),
        "tile-best.svg": tile("best day", s["busiest"][1], f"{s['busiest'][0]:%B %-d, %Y}", "yellow", 0.4),
        "activity.svg": activity(s),
        "heatmap.svg": heatmap(s),
    }
    for i, (name, blurb, lang, accent) in enumerate(FEATURED):
        out[f"repo-{name.lower()}.svg"] = repo_card(name, blurb, lang, accent, 0.1 + (i % 2) * 0.15)
    for fn, content in out.items():
        (CARDS / fn).write_text(content)
    print(f"wrote {len(out)} cards → {CARDS.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
