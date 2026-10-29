"""Pustaka kecil untuk generator Report v2: format angka (terdaftar untuk audit) dan grafik SVG inline."""
import re
from html import escape as esc

REG = set()          # token angka yang dihasilkan dari data (dipakai audit)


def _reg(s):
    REG.add(s)
    return s


def I(n):
    return _reg(f"{int(round(float(n))):,}".replace(",", "."))


def D(x, d=1):
    s = f"{float(x):.{d}f}"
    whole, _, frac = s.partition(".")
    whole = f"{int(whole):,}".replace(",", ".") if whole.lstrip("-").isdigit() and abs(int(whole)) >= 1000 else whole
    out = whole + ("," + frac if frac else "")
    _reg(out.lstrip("-").lstrip("+"))
    return out


def P(x, d=1):
    return D(float(x) * 100, d) + "%"


def pill(txt, kind=""):
    return f'<span class="pill{(" " + kind) if kind else ""}">{esc(txt)}</span>'


OK, PART, NO = (lambda t: pill(t)), (lambda t: pill(t, "p")), (lambda t: pill(t, "d"))
BLUE, HI, GREY, SOFT = "#1A73E8", "#E8710A", "#9AA0A6", "#AECBFA"


def table(head, rows, cls="rt"):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table class="{cls}"><tr>{h}</tr>{b}</table></div>'


def qa(qn, title, prio, ans, status="Terjawab", warn=False):
    return (f'<div class="qa{" w" if warn else ""}"><span class="qn">{qn}</span><div><div class="qt">{esc(title)}</div>'
            f'<div class="qm">{prio} · {pill(status, "p" if warn else "")}</div><p>{ans}</p></div></div>')


def legend(items):
    return '<div class="lg">' + "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>' for c, t in items) + "</div>"


def _nice(m):
    import math
    p = 10 ** math.floor(math.log10(m))
    f = m / p
    return p * (1 if f <= 1 else 2 if f <= 2 else 4 if f <= 4 else 8 if f <= 8 else 10)


def _fig(svg, label, small=False):
    return f'<div class="figw rc{" sm" if small else ""}">{svg.replace("<svg ", f"<svg role=\"img\" aria-label=\"{esc(label)}\" ", 1)}</div>'


def bars(items, fmt, label, h=270, ymax=None, rot=35, small=False):
    """items: (label, value, color, tooltip). Batang dari nol, ujung atas membulat."""
    W, L, B, T = 760, 52, 70 if rot else 34, 12
    ph = h - B - T
    n = len(items)
    bw = (W - L) / n
    m = ymax or _nice(max(v for _, v, _, _ in items) * 1.05)
    g = ""
    for k in range(5):
        y = T + ph - ph * k / 4
        g += f'<line x1="{L}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E8EAED"/><text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{fmt(m * k / 4)}</text>'
    b = ""
    for i, (lab, v, col, tip) in enumerate(items):
        bh = ph * v / m
        x, w = L + i * bw + bw * .16, bw * .68
        y, r = T + ph - bh, min(4, bw * .34, bh)
        b += (f'<path d="M{x:.1f},{T + ph}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{T + ph}Z" fill="{col}"><title>{esc(tip)}</title></path>')
        cx, ty = x + w / 2, T + ph + 16
        b += (f'<text x="{cx:.1f}" y="{ty}" text-anchor="end" transform="rotate(-{rot} {cx:.1f} {ty})">{esc(lab)}</text>' if rot
              else f'<text x="{cx:.1f}" y="{ty}" text-anchor="middle">{esc(lab)}</text>')
    svg = f'<svg viewBox="0 0 {W} {h}">{g}<line x1="{L}" x2="{W}" y1="{T + ph}" y2="{T + ph}" stroke="#BDC1C6"/>{b}</svg>'
    return _fig(svg, label, small)


def gbars(cats, series, fmt, label, h=280, rot=35):
    """series: (nama, warna, [nilai per kategori]); tooltip otomatis."""
    W, L, B, T = 760, 52, 70, 12
    ph = h - B - T
    n, k = len(cats), len(series)
    bw = (W - L) / n
    m = _nice(max(max(v) for _, _, v in series) * 1.05)
    g = ""
    for j in range(5):
        y = T + ph - ph * j / 4
        g += f'<line x1="{L}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E8EAED"/><text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{fmt(m * j / 4)}</text>'
    b = ""
    for i, c in enumerate(cats):
        for j, (nm, col, vals) in enumerate(series):
            w = bw * .8 / k
            x = L + i * bw + bw * .1 + j * w
            bh = ph * vals[i] / m
            b += f'<rect x="{x + 1:.1f}" y="{T + ph - bh:.1f}" width="{w - 2:.1f}" height="{bh:.1f}" rx="3" fill="{col}"><title>{esc(c)} | {esc(nm)}: {fmt(vals[i])}</title></rect>'
        cx, ty = L + i * bw + bw / 2, T + ph + 16
        b += f'<text x="{cx:.1f}" y="{ty}" text-anchor="end" transform="rotate(-{rot} {cx:.1f} {ty})">{esc(c)}</text>'
    svg = f'<svg viewBox="0 0 {W} {h}">{g}<line x1="{L}" x2="{W}" y1="{T + ph}" y2="{T + ph}" stroke="#BDC1C6"/>{b}</svg>'
    return _fig(svg, label)


def hbars(items, fmt, label, xmax, small=True):
    """items: (label, value, color, tooltip)."""
    W, L, R, rh = 760, 230, 60, 26
    h = len(items) * rh + 8
    b = ""
    for i, (lab, v, col, tip) in enumerate(items):
        y, w = i * rh + 4, (W - L - R) * v / xmax
        b += (f'<text x="{L - 8}" y="{y + 17}" text-anchor="end">{esc(lab)}</text>'
              f'<rect x="{L}" y="{y + 3}" width="{w:.1f}" height="{rh - 8}" rx="3" fill="{col}"><title>{esc(tip)}</title></rect>'
              f'<text x="{L + w + 6:.1f}" y="{y + 17}">{fmt(v)}</text>')
    svg = f'<svg viewBox="0 0 {W} {h}"><line x1="{L}" x2="{L}" y1="0" y2="{h}" stroke="#BDC1C6"/>{b}</svg>'
    return _fig(svg, label, small)


def lines(xlabels, series, fmt, label, h=270, zero=False, bands=(), band_label=""):
    """series: (nama, warna, lebar, [nilai]); bands: indeks titik yang diberi latar."""
    W, L, B, T = 760, 56, 30, 12
    ph = h - B - T
    n = len(xlabels)
    vals = [v for _, _, _, vs in series for v in vs]
    lo, hi = (0, _nice(max(vals) * 1.05)) if zero else (min(vals), max(vals))
    if not zero:
        pad = (hi - lo) * .1
        lo, hi = lo - pad, hi + pad
    X = lambda i: L + i / (n - 1) * (W - L - 8)
    Y = lambda v: T + ph - (v - lo) / (hi - lo) * ph
    g = ""
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        g += f'<line x1="{L}" x2="{W}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#E8EAED"/><text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{fmt(v)}</text>'
    st = max(1, n // 8)
    xl = "".join(f'<text x="{X(i):.1f}" y="{h - 8}" text-anchor="middle">{esc(xlabels[i])}</text>' for i in range(0, n, st))
    bd = "".join(f'<rect x="{X(i) - (W - L) / n / 2:.1f}" y="{T}" width="{(W - L) / n:.1f}" height="{ph}" fill="#FBBC04" opacity=".28"><title>{esc(band_label)} {esc(xlabels[i])}</title></rect>' for i in bands)
    pts = "".join(f'<path d="{"".join(("L" if i else "M") + f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vs))}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round"/>' for _, c, w, vs in series)
    hit = "".join(f'<circle cx="{X(i):.1f}" cy="{Y(vs[i]):.1f}" r="6" fill="transparent"><title>{esc(xlabels[i])} | {esc(nm)}: {fmt(vs[i])}</title></circle>' for nm, c, w, vs in series[-1:] for i in range(n))
    svg = f'<svg viewBox="0 0 {W} {h}">{g}{bd}<line x1="{L}" x2="{W}" y1="{T + ph}" y2="{T + ph}" stroke="#BDC1C6"/>{xl}{pts}{hit}</svg>'
    return _fig(svg, label)


def pareto_svg(codes, shares, cum, vital, tips, label, h=300):
    W, L, R, B, T = 760, 52, 44, 74, 12
    ph = h - B - T
    n = len(codes)
    bw = (W - L - R) / n
    m = _nice(max(shares) * 1.05)
    g = ""
    for k in range(5):
        y = T + ph - ph * k / 4
        g += (f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E8EAED"/><text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{round(m * k / 4 * 100)}%</text>'
              f'<text x="{W - R + 6}" y="{y + 4:.1f}">{k * 25}%</text>')
    b = ""
    for i in range(n):
        x, w = L + i * bw + bw * .15, bw * .7
        bh = ph * shares[i] / m
        b += f'<rect x="{x:.1f}" y="{T + ph - bh:.1f}" width="{w:.1f}" height="{bh:.1f}" rx="3" fill="{BLUE if vital[i] else SOFT}"><title>{esc(tips[i])}</title></rect>'
        cx, ty = x + w / 2, T + ph + 16
        b += f'<text x="{cx:.1f}" y="{ty}" text-anchor="end" transform="rotate(-40 {cx:.1f} {ty})">{codes[i]}</text>'
    ln = "".join(("L" if i else "M") + f"{L + i * bw + bw / 2:.1f},{T + ph - ph * cum[i]:.1f}" for i in range(n))
    y80 = T + ph - ph * .8
    svg = (f'<svg viewBox="0 0 {W} {h}">{g}<line x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}" stroke="#BDC1C6"/>'
           f'<line x1="{L}" x2="{W - R}" y1="{y80:.1f}" y2="{y80:.1f}" stroke="#5F6368" stroke-dasharray="4 3"/>{b}<path d="{ln}" fill="none" stroke="#3C4043" stroke-width="2"/></svg>')
    return _fig(svg, label)


NUM = re.compile(r"(?<![\w.,/-])[-+]?\d+(?:[.,]\d+)*")


def visible_text(html):
    h = re.sub(r"(?s)<(svg|script|style)\b.*?</\1>", " ", html)
    h = re.sub(r"(?s)<code>.*?</code>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"&\w+;", " ", h)


def audit(html, static):
    """Mengembalikan (jumlah token diperiksa, daftar token yang tidak berasal dari data dan tidak ada di whitelist)."""
    toks = [t.lstrip("+-").rstrip(".,") for t in NUM.findall(visible_text(html))]
    bad = sorted({t for t in toks if t not in REG and t not in static})
    return len(toks), bad


def cs(text):
    """Teks dari CSV hasil (format desimal titik) -> format Indonesia; angkanya didaftarkan untuk audit."""
    t = re.sub(r"(?<=\d)\.(?=\d)", ",", str(text))
    for tok in NUM.findall(t):
        REG.add(tok.lstrip("+-").rstrip(".,"))
    return t
