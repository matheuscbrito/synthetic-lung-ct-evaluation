"""Generic workbench mockup renderer (v3).

Reads one bundle shaped like the generic UI contract
(docs/planning/2026-10-27-workbench-generic-contract.md) and writes a slide deck.
It must not know any dataset, metric, optimizer or notebook by name: every label,
limit, colour slot and noun comes from the bundle.

usage: python render_v3.py bundle.json out.html
"""
import html, json, math, os, sys

B = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
SC = B["schema"]
DS = SC["dataset"]
ITEM = DS["item"]
GROUP = DS.get("group_by")
AXES = SC["axes"]
AX = {a["key"]: a for a in AXES}
MET = {m["key"]: m for m in SC["metrics"]}
TECH = {t["key"]: t for t in SC["techniques"]}
ST = {s["key"]: s for s in SC["statuses"]}
SEV = {k: s["severity"] for k, s in ST.items()}
GOOD = next(s["key"] for s in SC["statuses"] if s["tone"] == "good")
TONE = {"good": ("#2f9e57", "#e7f4ec", "#1f7a43"), "warn": ("#d9a21b", "#fbf1dc", "#9a6408"),
        "bad": ("#c0392b", "#fbe6e3", "#a83224"), "neutral": ("#b8bdbb", "#eeeeec", "#6b6b66")}
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#8a5cd1", "#d6456b", "#8f8c84"]
REF, BASE, CUR = DS["reference_version"], B["baseline"], B["current"]
ITEMS = B["items"]                      # {version: [item]}
items = ITEMS[CUR]
by_id = {i["id"]: i for i in items}
N = len(items)
FOCUS, CMP = B["focus"], B["compare_items"]
# versions are shown by their display id (reference, baseline or the synthesis id), never by folder name
LBL = {v["name"]: v.get("label") or v["name"] for v in B["versions"]}


def VL(name):
    return LBL.get(name, name)
ADD = SC.get("addons", {})


def esc(s):
    return html.escape(str(s))


def cap(s):
    return s[:1].upper() + s[1:]


def sg(x, d=1):
    t = f"{x:+.{d}f}"
    if float(t) == 0:
        t = f"{0:.{d}f}"
    return t.replace("-", "−")


def col(status):
    return TONE[ST[status]["tone"]][0]


def pill(status, text=None):
    c, bg, fg = TONE[ST[status]["tone"]]
    return f'<span class="pill" style="background:{bg};color:{fg}"><i style="background:{c}"></i>{esc(text or ST[status]["label"])}</span>'


def chip(status, text):
    _, bg, fg = TONE[ST[status]["tone"]]
    return f'<span class="cnt" style="color:{fg};background:{bg}">{text}</span>'


def metric_text(key, mv):
    m = MET[key]
    if mv is None or mv.get("available") is False:
        return "n/a"
    d = m.get("decimals", 2)
    if m["display"] == "z" and mv.get("z") is not None:
        t = f'{sg(mv["z"], d)} {m["unit"]}'
        if mv.get("ci"):
            t += f' [{sg(mv["ci"][0], d)}, {sg(mv["ci"][1], d)}]'
        return t
    v = mv.get("value")
    return "–" if v is None else f'{v:.{d}f}{"" if m["unit"] in ("", None) else (m["unit"] if m["unit"] == "%" else " " + m["unit"])}'


def axis_metrics(axis):
    return [m for m in SC["metrics"] if m["axis"] == axis]


def worst(item, axis):
    """Largest normalised deviation of an item on an axis (|z|, or value ÷ review limit)."""
    out = 0.0
    for m in axis_metrics(axis):
        mv = item["metrics"].get(m["key"]) or {}
        if mv.get("z") is not None:
            out = max(out, abs(mv["z"]))
        elif mv.get("value") is not None and m.get("limits"):
            out = max(out, abs(mv["value"]) / m["limits"]["review"])
    return out


def order(axis, its=None):
    return sorted(its or items, key=lambda i: (-SEV[i["verdicts"][axis]], -worst(i, axis), i["id"]))


def counts(axis, its=None):
    c = {k: 0 for k in ST}
    for i in its or items:
        c[i["verdicts"][axis]] += 1
    return c


# focus axis for screens that show one axis first: the axis with most non-good verdicts
FAX = max(AXES, key=lambda a: sum(i["verdicts"][a["key"]] != GOOD for i in items))["key"]

# ---------------------------------------------------------------- charts
def nice_max(v):
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    return next(k * e for k in (1, 2, 2.5, 5, 10) if k * e >= v)


def ticks(lo, hi, n=5):
    """Round tick values covering [lo, hi]."""
    raw = (hi - lo) / n or 1
    e = 10 ** math.floor(math.log10(raw))
    step = next(k * e for k in (1, 2, 2.5, 5, 10) if k * e >= raw)
    t, out = math.floor(lo / step) * step, []
    while t < hi + step - step * 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def curves_svg(p, w=560, h=200, colors=None):
    xs = [x for s in p["series"] for x in s["x"]] + (p["band"]["x"] if p.get("band") else [])
    ys = [y for s in p["series"] for y in s["y"] if y is not None] + ((p["band"]["lo"] + p["band"]["hi"]) if p.get("band") else [])
    logy = p["y"].get("scale") == "log"
    ys = [y for y in ys if y is not None and (not logy or y > 0)]
    x0, x1 = min(xs), max(xs)
    if logy:
        lo, hi = math.floor(math.log10(min(ys))), math.ceil(math.log10(max(ys)))
    else:
        lo, hi = min(0, min(ys)), max(ys)
    pl, pr, pt, pb = 46, 110, 10, 28

    def X(v):
        return pl + (v - x0) / ((x1 - x0) or 1) * (w - pl - pr)

    def Y(v):
        t = (math.log10(max(v, 10 ** lo)) - lo) / (hi - lo) if logy else (v - lo) / ((hi - lo) or 1)
        return pt + (1 - t) * (h - pt - pb)
    g = [f'<svg class="spec" viewBox="0 0 {w} {h}" preserveAspectRatio="none">']
    if not logy:
        lo, hi = min(ticks(lo, hi)), max(ticks(lo, hi))
    for t in (range(lo, hi + 1) if logy else ticks(lo, hi, 4)):
        y = Y(10 ** t if logy else t)
        lab = f'10<tspan dy="-5" font-size="8">{t}</tspan>' if logy else f"{t:g}"
        g.append(f'<line x1="{pl}" x2="{w-pr}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{pl-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{lab}</text>')
    for v in [t for t in ticks(x0, x1) if t <= x1]:
        g.append(f'<text x="{X(v):.1f}" y="{h-12}" class="ax" text-anchor="middle">{v:g}</text>')
    g.append(f'<text x="{(pl+w-pr)/2:.0f}" y="{h}" class="ax" text-anchor="middle">{esc(p["x"]["label"])}</text>')
    if p.get("band"):
        b = p["band"]
        top = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(b["x"], b["hi"]))
        bot = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in reversed(list(zip(b["x"], b["lo"]))))
        g.append(f'<polygon points="{top} {bot}" class="band"><title>{esc(b["label"])}</title></polygon>')
    for mk in p.get("markers", []):
        g.append(f'<line x1="{X(mk["x"]):.1f}" x2="{X(mk["x"]):.1f}" y1="{pt}" y2="{h-pb}" class="nyq"><title>{esc(mk["label"])}</title></line>')
    ends, k = [], 0
    for i, s in enumerate(p["series"]):
        if s.get("role") == "real":
            c = "#52514e"
        else:
            c = (colors or {}).get(s["label"]) or PALETTE[k % len(PALETTE)]
            k += 1
        pts = [(x, y) for x, y in zip(s["x"], s["y"]) if y is not None and (not logy or y > 0)]
        g.append(f'<path d="M{" L".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)}" class="line" style="stroke:{c};animation-delay:{.15*i:.2f}s"/>')
        ends.append([Y(pts[-1][1]), s["label"], c])
    ends.sort()
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 14)
    for y, lab, c in ends:
        g.append(f'<line x1="{w-pr+4}" x2="{w-pr+12}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:{c};stroke-width:2"/><text x="{w-pr+16}" y="{y+4:.1f}" class="lab">{esc(lab)}</text>')
    g.append("</svg>")
    return "".join(g)


def bars_svg(p, w=560, h=200):
    vals = [b["value"] for b in p["bars"]] + [p.get("zero", 0)]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * .1 or 1
    lo, hi = lo - pad, hi + pad
    pl, pr, pt, pb = 46, 16, 10, 30

    def Y(v):
        return pt + (hi - v) / (hi - lo) * (h - pt - pb)
    bw = (w - pl - pr) / len(p["bars"])
    z = p.get("zero", 0)
    g = [f'<svg class="spec" viewBox="0 0 {w} {h}" preserveAspectRatio="none">',
         f'<line x1="{pl}" x2="{w-pr}" y1="{Y(z):.1f}" y2="{Y(z):.1f}" class="zero"/><text x="{pl-8}" y="{Y(z)+4:.1f}" class="ax" text-anchor="end">{z:g}</text>']
    for i, b in enumerate(p["bars"]):
        x = pl + i * bw + bw * .22
        y0, y1 = sorted((Y(z), Y(b["value"])))
        g.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw*.56:.1f}" height="{max(1, y1-y0):.1f}" rx="4" class="wbar" style="animation-delay:{.05*i:.2f}s"><title>{b["value"]:.2f}</title></rect>')
        g.append(f'<text x="{x+bw*.28:.1f}" y="{h-10}" class="ax" text-anchor="middle">{esc(b["label"])}</text>')
    g.append("</svg>")
    return "".join(g)


def interval_svg(p, w=560, h=150):
    edges = [b["from"] for b in p["bands"]] + [b["to"] for b in p["bands"]]
    lo, hi = min(edges), max(edges)
    pl, pr, pt, pb = 20, 20, 14, 30

    def X(v):
        return pl + (min(hi, max(lo, v)) - lo) / (hi - lo) * (w - pl - pr)
    ys, yh = pt + 10, h - pt - pb - 10
    g = [f'<svg class="spec" viewBox="0 0 {w} {h}" style="height:{h}px">']
    for b in p["bands"]:
        g.append(f'<rect x="{X(b["from"]):.1f}" y="{ys}" width="{X(b["to"])-X(b["from"]):.1f}" height="{yh}" fill="{TONE[ST[b["status"]]["tone"]][1]}"/>')
    for v in sorted(set(edges)):
        g.append(f'<text x="{X(v):.1f}" y="{h-10}" class="ax" text-anchor="middle">{v:g}</text>')
    cy = ys + yh / 2
    if p.get("ci"):
        a, b = X(p["ci"][0]), X(p["ci"][1])
        g.append(f'<line x1="{a:.1f}" x2="{b:.1f}" y1="{cy}" y2="{cy}" stroke="#16150f" stroke-width="2.5"/><line x1="{a:.1f}" x2="{a:.1f}" y1="{cy-8}" y2="{cy+8}" stroke="#16150f" stroke-width="2.5"/><line x1="{b:.1f}" x2="{b:.1f}" y1="{cy-8}" y2="{cy+8}" stroke="#16150f" stroke-width="2.5"/>')
    g.append(f'<circle cx="{X(p["value"]):.1f}" cy="{cy}" r="6.5" fill="{col(p["status"])}" stroke="#fff" stroke-width="2"/>')
    ci = f' · [{sg(p["ci"][0], 2)}, {sg(p["ci"][1], 2)}]' if p.get("ci") else ""
    g.append(f'<text x="{X(p["value"]):.1f}" y="{pt+2}" class="lab" text-anchor="middle">{sg(p["value"], 2)} {esc(p.get("unit", ""))}{ci}</text></svg>')
    return "".join(g)


def matrix_html(p):
    vmax = max(v for pn in p["panels"] for row in pn["values"] for v in row) or 1
    out = []
    for pn in p["panels"]:
        n = len(pn["values"])
        cells = "".join(f'<i style="background:rgba(42,120,214,{(v/vmax)**.5:.3f})" title="{esc(p["rows"][r])} × {esc(p["cols"][c])}: {v:.3g}"></i>' for r, row in enumerate(pn["values"]) for c, v in enumerate(row))
        out.append(f'<div class="mx"><div class="eyebrow" style="margin-bottom:6px">{esc(pn["label"])}</div><div class="mxg" style="grid-template-columns:repeat({n},1fr)">{cells}</div></div>')
    return f'<div class="mxs">{"".join(out)}</div><div class="wtype">{esc(p["scale"]["label"])} · {len(p["rows"])} × {len(p["cols"])}</div>'


def chart(p, kind, **kw):
    return {"curves": curves_svg, "bars": bars_svg, "interval": interval_svg, "matrix": lambda q, **_: matrix_html(q)}[kind](p, **kw)


# ---------------------------------------------------------------- shell pieces
NAV = [("dataset", "Dataset", '<rect x="3" y="8" width="13" height="13" rx="2"/><path style="fill:none" d="M6.5 5.5H17a1.5 1.5 0 0 1 1.5 1.5v10.5"/><path style="fill:none" d="M10 3h9.5A1.5 1.5 0 0 1 21 4.5V15"/>'),
       # generators: a large and a small sparkle (synthesis); versions: clock with a back arrow (history)
       ("generators", "Generators", '<path d="M11 3.5l1.9 5.1 5.1 1.9-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9z"/><path d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>'),
       ("versions", "Versions", '<path style="fill:none" d="M4 12a8 8 0 1 0 2.4-5.7L4 8.6"/><path style="fill:none" d="M4 4.5v4.1h4.1"/><path style="fill:none" d="M12 8v4.2l2.8 1.8"/>')]


def rail(active):
    items_ = "".join(f'<div class="nav{" on" if k == active else ""}"><span class="ib"><svg viewBox="0 0 24 24">{v}</svg></span>{esc(lab)}</div>' for k, lab, v in NAV)
    return f'<nav class="rail"><div class="logo"><svg viewBox="0 0 5 5" class="glyph" aria-label="a"><path fill-rule="evenodd" fill="#fff" d="M0 0h4v1H0zM4 1h1v1H4zM0 2h4v3H0zM1 3v1h2V3z"/></svg></div>{items_}</nav>'


def dsw():
    if len(SC["datasets"]) < 2:
        return ""
    return '<div class="seg small dsw" data-seg title="Dataset">' + "".join(f'<span{" class=on" if d["key"] == DS["key"] else ""}>{esc(d["label"])}</span>' for d in SC["datasets"]) + "</div>"


def axis_seg(active, cls="small", grp=False):
    attr = "data-axis" if grp else "data-seg"
    return f'<div class="seg {cls}" {attr} style="margin:0">' + "".join(f'<span data-k="{a["key"]}"{" class=on" if a["key"] == active else ""}>{esc(a["label"])}</span>' for a in AXES) + "</div>"


def hidden(axis, active):
    return "" if axis == active else " hidden"


SLIDE = {}  # filled once the slide order is known


def ds_tabs(active):
    tabs = [("Overview", "dataset"), (cap(ITEM["singular"]), "item"), ("Compare", "compare")]
    return '<div class="seg gtabs" data-pages style="margin:0">' + "".join(f'<span data-go="{SLIDE[k]}"{" class=on" if k == active else ""}>{t}</span>' for t, k in tabs) + "</div>"


def gen_tabs(active):
    tabs = [("Benchmark", "bench")] + ([("Optimizers", "runs")] if ADD.get("optimizers") else []) + ([("Notebook", "exp")] if ADD.get("experiments") else [])
    if len(tabs) == 1:
        return ""
    return '<div class="seg gtabs" data-pages style="margin:0">' + "".join(f'<span data-go="{SLIDE[k]}"{" class=on" if t == active else ""}>{t}</span>' for t, k in tabs) + "</div>"


def tile(i, sel=False):
    dots = "".join(f'<span class="dot" data-grp="{a["key"]}" style="background:{col(i["verdicts"][a["key"]])}"{hidden(a["key"], FAX)}></span>' for a in AXES)
    return (f'<div class="tile{" sel" if sel else ""}" style="--i:{min(i_idx(i), 60)}"><img src="{B["thumbs"][i["id"]]}" alt="">'
            f'<div class="meta"><span>{esc(i["label"])}</span>{dots}</div></div>')


_IDX = {i["id"]: k for k, i in enumerate(order(FAX))}


def i_idx(i):
    return _IDX[i["id"]]


def tri(i):
    return "".join(f'<i class="dot" style="background:{col(i["verdicts"][a["key"]])}" title="{esc(a["label"])}"></i>' for a in AXES)


# ---------------------------------------------------------------- dataset
def limit_txt(m, which):
    L = m.get("limits")
    if not L or L.get(which) is None:
        return "–"
    sym = {"abs_z": "|z| &gt; ", "abs_value": "|x| &gt; ", "above": "&gt; ", "below": "&lt; "}[L["kind"]]
    unit = m["unit"] if L["kind"] != "abs_z" else ""
    return f'{sym}{L[which]:g}{"%" if unit == "%" else ""}'


def how_to_read():
    rows = "".join(f'<div class="lrow"><span>{esc(m["label"])} <span class="sub">· {esc(AX[m["axis"]]["label"])}</span></span><span class="mono">{limit_txt(m, "review")}</span><span class="mono">{limit_txt(m, "reject")}</span><span class="mono">{"–" if m.get("repeatability") is None else f"{m["repeatability"]:.2f} {esc(m["unit"])}"}</span></div>' for m in SC["metrics"])
    return (f'<details class="how"><summary class="chip">How to read <span class="chev">▾</span></summary><div class="panel"><div class="lrow lh"><span>Metric</span><span>Review</span><span>Reject</span><span>Repeatability</span></div>{rows}'
            f'<div class="src2 mono" style="margin-top:8px">Reference {esc(VL(REF))} · {N} {esc(ITEM["plural"])}</div></div></details>')


def kpi_block(axis):
    c = counts(axis)
    rest = "".join(f'<div class="row">{esc(ST[k]["label"])} <b class="count" data-to="{c[k]}">0</b></div>' for k in sorted(ST, key=SEV.get) if k != GOOD and c[k])
    ordered = order(axis)
    zmax = max(worst(i, axis) for i in items) or 1
    if N <= 60:
        bars = "".join(f'<i style="--h:{min(100, worst(i, axis)/zmax*100):.0f}%;background:{col(i["verdicts"][axis])};--i:{min(k, 80)}"></i>' for k, i in enumerate(ordered))
        blabel = f'Worst deviation per {esc(ITEM["singular"])}'
    else:  # many items: histogram of the worst deviation, stacked by status
        nb = 30
        bins = [{} for _ in range(nb)]
        for i in items:
            b = bins[min(nb - 1, int(worst(i, axis) / zmax * nb))]
            b[i["verdicts"][axis]] = b.get(i["verdicts"][axis], 0) + 1
        top = max(sum(b.values()) for b in bins) or 1
        bars = "".join(f'<i class="stk" style="--h:{sum(b.values())/top*100:.0f}%;--i:{k}">' + "".join(f'<b style="flex:{b[st]};background:{col(st)}"></b>' for st in sorted(b, key=SEV.get, reverse=True)) + "</i>" for k, b in enumerate(bins))
        blabel = f'{cap(ITEM["plural"])} by worst deviation'

    techs = sorted({t for i in items for t in i["techniques"].get(axis, {})}, key=lambda t: list(TECH).index(t))
    stat = " · ".join(f'{esc(TECH[t]["label"])} <b>{sum(i["techniques"][axis].get(t, GOOD) != GOOD for i in items)}</b>' for t in techs)
    nums = " · ".join(f'<b class="count" style="color:{TONE[ST[k]["tone"]][2]}" data-to="{c[k]}">0</b> {esc(ST[k]["label"].lower())}' for k in sorted(ST, key=SEV.get) if c[k] or k == GOOD)
    return (f'<div class="vs" data-grp="{axis}"{hidden(axis, FAX)}>'
            f'<div><div class="vsn">{nums} <span class="sub">of {N}</span></div>{status_bar(c, wide=True)}</div>'
            f'<div><div class="eyebrow">{blabel}</div><div class="bars mini">{bars}</div></div>'
            f'<div><div class="eyebrow">Out of range</div><div class="vst">{stat}</div></div></div>')


def slide_dataset():
    ordered = order(FAX)
    if GROUP:
        groups = {}
        for i in ordered:
            groups.setdefault(i["group"], []).append(i)
        keys = sorted(groups, key=lambda g: (-max(SEV[i["verdicts"][FAX]] for i in groups[g]), g))
        grid = "".join(f'<div class="group"><span class="eyebrow ink">{esc(GROUP["label"])} {esc(g)}</span><span class="sub">{len(groups[g])} {esc(ITEM["plural"])}</span></div><div class="grid">{"".join(tile(i, i["id"] == FOCUS) for i in groups[g])}</div>' for g in keys)
        gsub = f' · {len({i["group"] for i in items})} {esc(GROUP["label"].lower())}s'
        gfilter = f'<div class="chip">All {esc(GROUP["label"].lower())}s ▾</div>'
    else:
        grid = f'<div class="group"><span class="eyebrow ink">All {esc(ITEM["plural"])}</span><span class="sub">worst first</span></div><div class="grid">{"".join(tile(i, i["id"] == FOCUS) for i in ordered)}</div>'
        gsub, gfilter = "", ""
    main = f'''<main>
<div class="head"><div><div class="eyebrow">Dataset · {esc(DS["mode_label"])}</div><h1>{esc(cap(ITEM["plural"]))}</h1><div class="sub">{N} {esc(ITEM["plural"])}{gsub}</div></div><div class="hr">{ds_tabs("dataset")}{dsw()}<div class="chip ver">Version <b>{esc(VL(CUR))}</b> ▾</div></div></div>
<div class="vstrip">{axis_seg(FAX, "small", grp=True)}{"".join(kpi_block(a["key"]) for a in AXES)}</div>
<div class="filters"><div class="chip">All statuses ▾</div><div class="chip">Any technique ▾</div>{gfilter}<div class="chip">Sort: worst first ▾</div><div class="chip search">⌕ Search {esc(ITEM["singular"])}</div>{how_to_read()}</div>
<div class="scroll">{grid}</div></main>'''
    return f'<div class="win">{rail("dataset")}{main}</div>'


# ---------------------------------------------------------------- item
def reason_text(r):
    m = MET[r["metric"]]
    lim = r.get("limit") or "review"
    d = m.get("decimals", 2)
    if r.get("note"):
        return f'{m["label"]}: {r["note"]}.'
    L = m.get("limits") or {}
    if r.get("z") is not None:
        thr = r.get("limit_value") if r.get("limit_value") is not None else L.get(lim)
        ci = f' [{sg(r["ci"][0], d)}, {sg(r["ci"][1], d)}]' if r.get("ci") else ""
        return f'{m["label"]} is {r["direction"]} than real: {sg(r["z"], d)} {m["unit"]}{ci}, past the {lim} limit ({thr:g}).'
    thr = r.get("limit_value") if r.get("limit_value") is not None else L.get(lim)
    unit = m["unit"] if m["unit"] == "%" else f' {m["unit"]}'
    side = "above" if r.get("direction") != "lower" else "below"
    return f'{m["label"]} reads {r["value"]:.{d}f}{unit}, {side} the {lim} limit ({thr:g}{unit}).'


def why_block(i):
    parts = []
    for a in AXES:
        rs = [r for r in i["reasons"] if r["axis"] == a["key"]]
        if rs:
            lis = "".join(f'<li><i class="dot" style="background:{col(r["status"])}"></i><span>{esc(reason_text(r))}</span></li>' for r in rs)
            parts.append(f'<div class="wg"><span class="eyebrow">{esc(a["label"])}</span><ul>{lis}</ul></div>')
    n = len(i["reasons"])
    body = "".join(parts) or '<div class="sub" style="margin-top:6px">Every metric is within its limits.</div>'
    return f'<details class="why" open><summary><b>Why</b> <span class="sub">{n} reason{"s" if n != 1 else ""} behind the verdicts</span><span class="chev">▾</span></summary>{body}</details>'


def metric_rows(i, axis):
    return "".join(f'<div class="mrow"><span>{esc(m["label"])}</span><span class="mono">{metric_text(m["key"], i["metrics"].get(m["key"]))}</span><i class="dot" style="background:{col((i["metrics"].get(m["key"]) or {}).get("status", "inconclusive"))}"></i></div>' for m in axis_metrics(axis))


def slide_item():
    i = by_id[FOCUS]
    strip = "".join(f'<img class="fs{" cur" if x["id"] == FOCUS else ""}" style="border-color:{col(x["verdicts"][FAX])}" src="{B["thumbs"][x["id"]]}">' for x in order(FAX)[:48])
    others = [v for v in B["pane_versions"] if v != CUR]
    P = B["panes"]
    ov = f'<img class="roi" src="{P["overlay"]}">' if P.get("overlay") else ""
    mid = "".join(f'<img class="mid{" on" if k == 0 else ""}" data-v="{esc(v)}" src="{P[v]}">' for k, v in enumerate(others))
    cap_mid = "".join(f'<div class="cap mid{" on" if k == 0 else ""}" data-v="{esc(v)}"><span>Synthetic · {esc(VL(v))}</span><span class="tri">{tri({x["id"]: x for x in ITEMS[v]}[FOCUS])}</span></div>' for k, v in enumerate(others))
    panes = (f'<div class="pane"><div class="canvas"><img src="{P["real"]}">{ov}</div><div class="cap"><span>Original</span><span class="sub">shared window</span></div></div>'
             f'<div class="pane"><div class="canvas">{mid}{ov}</div>{cap_mid}</div>'
             f'<div class="pane"><div class="canvas"><img src="{P[CUR]}">{ov}</div><div class="cap"><span>Synthetic · {esc(VL(CUR))}</span><span class="tri">{tri(i)}</span></div></div>')
    ins = SC["inspectors"]
    tabs = "".join(f'<span data-t="{x["key"]}"{" class=on" if k == 0 else ""}>{esc(x["label"])}</span>' for k, x in enumerate(ins))
    pv = "".join(f'<div class="tool{" on" if k == 0 else ""}" data-p="{x["key"]}">{chart(B["inspect"][x["key"]], x["chart"], **({"w": 960, "h": 215} if x["chart"] in ("curves", "bars") else {}))}{"<div class=wtype>" + esc(B["inspect"][x["key"]]["note"]) + "</div>" if B["inspect"][x["key"]].get("note") else ""}</div>' for k, x in enumerate(ins))
    vh = "".join(f'<div><div class="eyebrow">{esc(a["label"])}</div>{pill(i["verdicts"][a["key"]])}</div>' for a in AXES)
    groups = "".join(f'<div class="eyebrow gc">{esc(a["label"])}</div>{metric_rows(i, a["key"])}' for a in AXES)
    facts = "".join(f'<div class="mrow"><span>{esc(f["label"])}</span><span class="mono">{esc(f["value"])}</span><i></i></div>' for f in i.get("facts", []))
    grp = f'<span class="sub">{esc(GROUP["label"])} {esc(i["group"])}</span>' if GROUP else ""
    main = f'''<main class="slice">
<div class="crumbs"><span>{esc(VL(CUR))}</span><span>›</span><b>{esc(i["label"])}</b>{grp}<div class="hr" style="margin-left:auto">{ds_tabs("item")}{axis_seg(FAX)}</div></div>
<div class="filmstrip">{strip}</div>
<div class="sgrid"><div>
<div class="cmprow"><span class="eyebrow">Compare with</span><div class="seg small" data-cmp style="margin:0">{"".join(f'<span{" class=on" if k == 0 else ""} data-v="{esc(v)}">{esc(VL(v))}</span>' for k, v in enumerate(others))}</div><span class="sub">Original and syntheses share one intensity window</span></div>
<div class="panes">{panes}</div>
<div class="tabs" data-tabs>{tabs}</div>
<div class="toolcard">{pv}</div>
</div>
<div class="verdict"><div class="vhead" style="grid-template-columns:repeat({len(AXES)},1fr)">{vh}</div>{why_block(i)}{groups}
{f'<div class="eyebrow gc">Facts</div>{facts}' if facts else ""}</div></div></main>'''
    return f'<div class="win">{rail("dataset")}{main}</div>'


# ---------------------------------------------------------------- generators › benchmark
CHG = {"improved": ("▲", "#1f7a43", "Improved"), "worsened": ("▼", "#a83224", "Worsened"), "same": ("＝", "#8f8c84", "Same")}
RES = {"improved": GOOD, "worse": next(s["key"] for s in SC["statuses"] if s["tone"] == "bad"), "small": "inconclusive", "same": "inconclusive"}
RUNS = B.get("runs")
RUN_LABEL = {r["key"]: r["label"] for r in (RUNS or {}).get("runs", [])}


def status_bar(c, wide=False):
    tot = sum(c.values()) or 1
    return f'<div class="sbar{" wide" if wide else ""}">' + "".join(f'<i style="flex:{c[k]/tot:.3f};background:{col(k)}" title="{esc(ST[k]["label"])} {c[k]}"></i>' for k in sorted(ST, key=SEV.get) if c.get(k)) + "</div>"


def slide_bench():
    bd = B["board"]
    vs = sorted(bd["versions"], key=lambda g: (g["name"] != BASE, g["name"] != CUR, g["name"]))
    compact = len(AXES) > 4
    shown = [k for k in sorted(ST, key=SEV.get) if k != "inconclusive"]
    rows = []
    for k, g in enumerate(vs):
        vb = g.get("vs_baseline") or []
        up, dn = sum(v["result"] == "improved" for v in vb), sum(v["result"] == "worse" for v in vb)
        tag = '<span class="pill base">baseline</span>' if g["name"] == BASE else f'<span class="pill" style="background:#e7f4ec;color:#1f7a43">{up} better</span> <span class="pill" style="background:{"#fbe6e3" if dn else "#eeeeec"};color:{"#a83224" if dn else "#6b6b66"}">{dn} worse</span>'
        sub = esc(g.get("subtitle", ""))
        if g.get("provenance") and g["provenance"]["run"] in RUN_LABEL:
            sub += f'<br><span class="otag" data-go="{SLIDE["runs"]}">see in Optimizers ↗</span>'
        cells = "".join(f'<div>{status_bar(g["counts"][a["key"]]) if compact else "".join(chip(s, g["counts"][a["key"]].get(s, 0)) for s in shown)}</div>' for a in AXES)
        rows.append(f'<div class="trow{" expanded" if g["name"] == CUR else ""}" style="--i:{k}"><div><b>{esc(VL(g["name"]))}</b><div class="sub">{sub}</div></div>{cells}<div>{tag}</div></div>')
    cols = f'grid-template-columns:1.25fr {" ".join(["1fr"] * len(AXES))} 1.5fr'
    head = "".join(f'<div>{esc(a["label"])}</div>' for a in AXES)
    cur_g = next(g for g in vs if g["name"] == CUR)
    IND = {x["key"]: x for x in SC["indicators"]}
    ind = [v for v in cur_g.get("vs_baseline", []) if v["result"] in ("improved", "worse")]
    irows = "".join(f'<div class="irow"><span>{esc(IND[v["indicator"]]["label"])}</span><span class="mono">{sg(v["gain"], 2)} [{sg(v["ci"][0], 2)}, {sg(v["ci"][1], 2)}]</span>{pill(RES[v["result"]], "improved" if v["result"] == "improved" else "worse")}</div>' for v in ind[:9])
    T = B["transitions"]

    # transition totals as one compact line per axis (no KPI cards)
    def tsum(t):
        n_w, n_i = sum(x["change"] == "worsened" for x in t), sum(x["change"] == "improved" for x in t)
        n_a = sum(x["became_approved"] for x in t)
        return (f'<b style="color:#a83224">▼ {n_w}</b> worsened · <b style="color:#1f7a43">▲ {n_i}</b> improved · '
                f'<b>{n_a}</b> became {esc(ST[GOOD]["label"].lower())} <span class="sub">of {N}</span>')
    tline = "".join(f'<div class="tsum" data-grp="{a["key"]}"{hidden(a["key"], FAX)}>{tsum(T[a["key"]])}</div>' for a in AXES)
    # cohort tests become rows of the indicators card
    crow = ""
    for c in cur_g.get("cohort", []):
        test = next(t for t in SC["cohort_tests"] if t["key"] == c["test"])
        det = " · ".join(f'{esc(d["label"])} {esc(d["value"])}' for d in c["detail"])
        crow += f'<div class="irow"><span>{esc(test["label"])}</span><span class="mono">{det}</span>{pill(c["result"]["status"], c["result"]["label"])}</div>'
    tb = ""
    for a in AXES:
        t = T[a["key"]]
        body = "".join(
            f'<div class="xr"><span><b>{esc(by_id[x["id"]]["label"])}</b>{f" <span class=sub>{esc(by_id[x["id"]]["group"])}</span>" if GROUP else ""}</span><span class="ba">{pill(x["before"])}<em>→</em>{pill(x["after"])}</span>'
            f'<span class="chg" style="color:{CHG[x["change"]][1]}">{CHG[x["change"]][0]} {CHG[x["change"]][2]}</span></div>'
            for x in sorted(t, key=lambda x: ({"worsened": 0, "improved": 1, "same": 2}[x["change"]], x["id"])) if x["change"] != "same")
        tb += f'<div data-grp="{a["key"]}"{hidden(a["key"], FAX)}>{body or f"<div class=sub style=padding:14px>No {esc(ITEM["singular"])} changed verdict.</div>"}</div>'
    main = f'''<main class="gen">
<div class="head"><div><div class="eyebrow">Generators · vs baseline</div><h1>Benchmark</h1><div class="sub">Same {N} {esc(ITEM["plural"])} · {len(vs)} versions · {esc(VL(CUR))} vs {esc(VL(BASE))}</div></div><div class="hr">{gen_tabs("Benchmark")}{dsw()}<div class="chip ver">vs <b>{esc(VL(BASE))}</b> ▾</div></div></div>
<div class="gcols" style="margin-top:22px"><div class="gleft"><div class="table"><div class="thead" style="{cols}"><div>Generator</div>{head}<div>vs baseline</div></div>{"".join(r.replace('class="trow', f'style="{cols}" class="trow', 1) for r in rows)}</div>
<div class="sub" style="margin:6px 4px 0;font-size:12px">{" · ".join(f"{esc(ST[s]["label"])}" for s in shown)} counts per axis · indicators compare {esc(VL(CUR))} with {esc(VL(BASE))}, 95% CI</div>
<div class="card irows"><div class="eyebrow ink">{esc(VL(CUR))} · indicators with a clear difference</div>{crow}{irows or "<div class=sub style=padding-top:8px>No clear difference.</div>"}</div></div>
<div class="card gright"><div class="ghead"><div class="eyebrow ink">Transitions · {esc(VL(BASE))} → {esc(VL(CUR))}</div>{axis_seg(FAX, grp=True)}</div>{tline}<div class="xtable">{tb}</div></div></div></main>'''
    return f'<div class="win">{rail("generators")}{main}</div>'


# ---------------------------------------------------------------- generators › optimizers
def run_curve(R, w=700, h=440):
    runs = R["runs"]
    obj = R["objective"]
    xmax = max(c["x"] for r in runs for c in r["curve"]) or 1
    ys = [c["y"] for r in runs for c in r["curve"]] + ([obj["goal"]] if obj.get("goal") is not None else [])
    yt = ticks(min(0, min(ys)), max(ys) * 1.08)
    ymin, ymax = yt[0], yt[-1]
    pl, pr, pt, pb = 48, 150, 12, 44

    def X(v):
        return pl + v / xmax * (w - pl - pr)

    def Y(v):
        return pt + (1 - (v - ymin) / (ymax - ymin)) * (h - pt - pb)
    u = obj["unit"]
    g = [f'<svg class="spec" viewBox="0 0 {w} {h}" style="height:{h}px">']
    for v in yt:
        g.append(f'<line x1="{pl}" x2="{w-pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/><text x="{pl-8}" y="{Y(v)+4:.1f}" class="ax" text-anchor="end">{v:.3g}{u if u == "%" else ""}</text>')
    for v in [t for t in ticks(0, xmax) if t <= xmax]:
        g.append(f'<text x="{X(v):.1f}" y="{h-24}" class="ax" text-anchor="middle">{v:g}</text>')
    g.append(f'<text x="{(pl+w-pr)/2:.0f}" y="{h-4}" class="ax" text-anchor="middle">{esc(R["budget_axis"]["label"])}</text>')
    if obj.get("goal") is not None:
        g.append(f'<line x1="{pl}" x2="{w-pr}" y1="{Y(obj["goal"]):.1f}" y2="{Y(obj["goal"]):.1f}" class="nyq" style="stroke:#16150f"/><text x="{pl+6}" y="{Y(obj["goal"])-5:.1f}" class="ax">goal {obj["goal"]:g}{u if u == "%" else " " + u}</text>')
    ends = []
    for i, r in enumerate(runs):
        p = r["curve"]
        c = PALETTE[i % len(PALETTE)]
        d = f"M{X(p[0]['x']):.1f},{Y(p[0]['y']):.1f}" + "".join(f" H{X(q['x']):.1f} V{Y(q['y']):.1f}" for q in p[1:])
        g.append(f'<g class="run" data-m="{esc(r["key"])}"><path d="{d}" class="line" style="stroke:{c};animation-delay:{.2*i:.1f}s"/></g>')
        ends.append([Y(p[-1]["y"]), f'{r["label"]} {p[-1]["y"]:.1f}{u if u == "%" else ""}', c, r["key"]])
    ends.sort()
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 15)
    for y, lab, c, key in ends:
        g.append(f'<g class="run" data-m="{esc(key)}"><line x1="{w-pr+4}" x2="{w-pr+12}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:{c};stroke-width:2"/><text x="{w-pr+16}" y="{y+4:.1f}" class="lab">{esc(lab)}</text></g>')
    g.append("</svg>")
    return "".join(g)


def fmtp(v):
    return f"{v:g}" if isinstance(v, (int, float)) else esc(v)


def stage_cell(st):
    return f'<span class="sc">{esc(st.get("stage") or "")}</span>'


def slide_runs():
    R = RUNS
    obj, u = R["objective"], R["objective"]["unit"]
    pk = [p for p in R["params"]]
    cards, tabs = [], []
    for i, r in enumerate(R["runs"]):
        s = r["summary"]
        c = PALETTE[i % len(PALETTE)]
        bud = f'{s["used"]}/{s["budget"]}' if s.get("budget") else f'{s["used"]}'
        prm = " · ".join(f'{p["label"]} {fmtp(r["best_params"][p["key"]])}' for p in pk if p["key"] in r["best_params"])
        reach = next((q["x"] for q in r["curve"] if q["y"] >= s["best"] - 1e-9), r["curve"][-1]["x"])
        cards.append((s["best"], f'''<div class="rkrow" data-m="{esc(r["key"])}" title="Best configuration: {esc(prm)}"><span class="rkname"><i class="key" style="background:{c}"></i>{esc(r["label"])}</span>
<span class="mono rkbest">{sg(s["best"])}{esc(u) if u == "%" else " " + esc(u)}</span><span class="mono">{reach:g}</span><span class="mono">{s["evaluated"]}</span><span class="mono">{bud}</span></div>'''))
        keys = [p for p in pk if any(p["key"] in st["params"] for st in r["steps"])]
        has_stage = any(st.get("stage") for st in r["steps"])
        has_wl = any(st.get("wins") is not None for st in r["steps"])
        tpl = f'grid-template-columns:44px{" 54px" if has_stage else ""} repeat({len(keys)},minmax(0,1fr)) 84px{" 54px" if has_wl else ""}'
        body = "".join(f'<div class="strow" style="{tpl}"><span class="mono">#{esc(st["id"])}</span>{stage_cell(st) if has_stage else ""}'
                       + "".join(f'<span class="mono prm">{fmtp(st["params"].get(p["key"], "–"))}</span>' for p in keys)
                       + f'<span class="mono chipv" style="background:{TONE[ST[st["outcome"]["status"]]["tone"]][1]};color:{TONE[ST[st["outcome"]["status"]]["tone"]][2]}" title="{esc(st["outcome"]["label"])}">{sg(st["score"])}{esc(u) if u == "%" else ""}{" ★" if st.get("is_best") else ""}</span>'
                       + (f'<span class="mono wl">{st["wins"]}/{st["losses"]}</span>' if has_wl else "") + "</div>" for st in r["steps"])
        hdr = (f'<div class="strow sth" style="{tpl}"><span>#</span>{"<span>Stage</span>" if has_stage else ""}' + "".join(f'<span>{esc(p["label"])}</span>' for p in keys)
               + f'<span title="{esc(obj["label"])}">Score</span>{"<span>W / L</span>" if has_wl else ""}</div>')
        tabs.append(f'<div class="stbl" data-m="{esc(r["key"])}"[[H{esc(r["key"])}]]>{hdr}<div class="stbody">{body}</div></div>')
    src = " · ".join(f'{esc(s["label"])}' for s in R["sources"])
    cards = [h for _, h in sorted(cards, key=lambda t: -t[0])]
    cards[0] = cards[0].replace('class="rkrow"', 'class="rkrow on"', 1)
    top = next(r for r in R["runs"] if f'data-m="{esc(r["key"])}"' in cards[0])
    bax = esc(R["budget_axis"]["label"])
    rank = (f'<div class="card rkcard"><div class="eyebrow ink" style="margin-bottom:6px">Optimizers · {len(R["runs"])}</div>'
            f'<div class="rkrow rkh"><span>Optimizer</span><span>Best</span><span title="{bax} until the best">To best</span><span title="configurations evaluated">Configs</span><span title="{bax} / budget">Used</span></div>{"".join(cards)}</div>')
    main = f'''<main>
<div class="head"><div><div class="eyebrow">Generators · optimizers</div><h1>Optimizers</h1><div class="sub">Searches for generator settings · {esc(obj["label"])} · source {src}</div></div><div class="hr">{gen_tabs("Optimizers")}</div></div>
<div class="ocols2"><div class="toolcard"><div class="eyebrow ink" style="margin-bottom:8px">Best {esc(obj["label"].lower())} vs {bax}</div>{run_curve(R, h=600)}</div>
<div class="ocright">{rank}<div class="card stcard"><div class="eyebrow ink" style="margin-bottom:8px">Steps · <span id="stname">{esc(top["label"])}</span></div>{"".join(tabs)}</div></div></div></main>'''
    for r in R["runs"]:
        main = main.replace(f'[[H{esc(r["key"])}]]', "" if r is top else " hidden")
    return f'<div class="win">{rail("generators")}{main}</div>'


# ---------------------------------------------------------------- generators › notebook
EXP = B.get("experiments")


def slide_exp():
    E = EXP
    scope_keys = [s["key"] for s in E["scopes"]]

    def last(x):
        ks = [k for k in scope_keys if x["scores"].get(k) is not None]
        return x["scores"][ks[-1]] if ks else None
    items_ = []
    for x in E["experiments"]:
        _, bg, fg = TONE[ST[x["outcome"]["status"]]["tone"]]
        v = last(x)
        txt = "n/a" if v is None else sg(v) + (E["objective"]["unit"] if E["objective"]["unit"] == "%" else "")
        items_.append(f'<div class="xi{" on" if x.get("is_best") else ""}" data-x="{esc(x["id"])}"><span class="xid mono">{esc(x["id"])}</span><span class="xch">{esc(x["change"])}</span>'
                      f'<span class="xv mono" style="background:{bg};color:{fg}">{txt}</span>{"<i class=xbest>★</i>" if x.get("is_best") else ""}</div>')
    secs = "".join(f'<div class="eyebrow ink" style="margin-top:{12 if k else 0}px">{esc(s["title"])}</div><ul>' + "".join(f'<li>{"<b>" + esc(it["head"]) + "</b> " if it.get("head") else ""}<span>{esc(it["body"][:150])}{"…" if len(it["body"]) > 150 else ""}</span></li>' for it in s["items"][:4]) + "</ul>" for k, s in enumerate(E["sections"]))
    main = f'''<main>
<div class="head"><div><div class="eyebrow">Generators · optimizers</div><h1>Notebook</h1><div class="sub">Experiments, lessons and next steps · source {esc(E["source"]["label"])}</div></div><div class="hr">{gen_tabs("Notebook")}</div></div>
<div class="expbody"><div class="hist"><div class="chip search" style="width:100%">⌕ Filter experiments</div><div class="xlist"><div class="eyebrow" style="margin:16px 0 6px">Experiments · {len(items_)}</div>{"".join(items_)}</div></div>
<div class="thread"><div class="xdetail" id="xdetail"></div>
<div class="xgrid"><div class="toolcard"><div class="eyebrow" style="margin-bottom:6px">Trajectory · {esc(E["objective"]["label"])}</div><div id="xtraj"></div></div>
<div class="card lessons">{secs}</div></div>
</div></div></main>'''
    return f'<div class="win">{rail("generators")}{main}</div>'


# ---------------------------------------------------------------- compare
def slide_compare():
    cols_ = []
    for k, c in enumerate(CMP):
        i = by_id[c]
        rows = "".join(f'<div class="crow"><span>{esc(m["label"])}</span><span class="mono">{metric_text(m["key"], i["metrics"].get(m["key"])).split(" [")[0]}</span><i class="dot" style="background:{col((i["metrics"].get(m["key"]) or {}).get("status", "inconclusive"))}"></i></div>' for m in SC["metrics"])
        vp = "".join(f'<div><div class="eyebrow" style="font-size:10.5px">{esc(a["label"])}</div>{pill(i["verdicts"][a["key"]])}</div>' for a in AXES)
        cols_.append(f'<div class="ccol" style="--i:{k}"><div class="chead"><i class="key" style="background:{PALETTE[k]}"></i><b>{esc(i["label"])}</b><span class="sub">{esc(i["group"]) if GROUP else ""}</span></div><img src="{B["compare_images"][c]}"><div class="vp">{vp}</div><div class="cscroll">{rows}</div></div>')
    ci = B.get("compare_inspect")
    tool = ""
    if ci:
        x = next(x for x in SC["inspectors"] if x["key"] == ci["inspector"])
        colors = {by_id[c]["label"]: PALETTE[k] for k, c in enumerate(CMP)}
        tool = f'<div class="toolcard"><div class="eyebrow" style="margin-bottom:8px">{esc(x["label"])} · synthetic{" · band = " + esc(ci["payload"]["band"]["label"]) if ci["payload"].get("band") else ""}</div>{chart(ci["payload"], x["chart"], w=1380, h=190, colors=colors)}</div>'
    main = f'''<main>
<div class="head"><div><div class="eyebrow">Compare · {esc(VL(CUR))}</div><h1 class="ids">{"".join(f'<span><i class="key" style="background:{PALETTE[k]}"></i>{esc(by_id[c]["label"])}</span>' for k, c in enumerate(CMP))}</h1><div class="sub">Shared intensity window per {esc(ITEM["singular"])}</div></div><div class="hr">{ds_tabs("compare")}<div class="seg small" data-seg style="margin:0"><span class="on">Synthetic</span><span>Real</span></div></div></div>
<div class="ccols">{"".join(cols_)}</div>{tool}</main>'''
    return f'<div class="win">{rail("dataset")}{main}</div>'


# ---------------------------------------------------------------- versions
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def slide_versions():
    rows = []
    for k, v in enumerate(B["versions"]):
        d = v["added"][:10]
        date = f'{int(d[8:10])} {MONTHS[int(d[5:7])-1]}'
        tag = '<span class="pill base">ruler reference</span>' if v["is_reference"] else '<span class="okc">✓</span>'
        rm = "" if v["is_reference"] else '<span class="ghost">Remove</span>'
        warn = "".join(f' · {w["count"]} {esc(w["label"])}' for w in v.get("warnings", []))
        prov = f' · from {esc(RUN_LABEL.get(v["provenance"]["run"], v["provenance"]["run"]))} #{esc(v["provenance"]["step"])}' if v.get("provenance") else ""
        rows.append(f'<div class="vrow" style="--i:{k}"><div><b>{esc(VL(v["name"]))}</b><div class="sub">{esc(v["mode_label"])} · {v["n_items"]} {esc(ITEM["plural"])} · {v["n_common"]} common pairs{warn}{prov}</div></div><span class="mono sub">{date}</span>{rm}{tag}</div>')
    D = B.get("detected", [])
    det = "".join(f'<div class="vrow"><div><b>{esc(d["name"])}</b><div class="sub mono">{esc(d["folder"])}</div></div><span class="dark sm">Add</span></div>' for d in D) or \
        '<div class="empty"><div class="eb">◌</div><b>No runs detected</b><div class="sub">Completed runs found in the configured run folders appear here, ready to add as a version.</div></div>'
    axes_txt = ", ".join(a["label"].lower() for a in AXES)
    main = f'''<main>
<div class="head"><div><div class="eyebrow">History · {esc(DS["mode_label"])}</div><h1>Versions</h1><div class="sub">Each version is measured once against the {esc(VL(REF))} reference</div></div><div class="hr">{dsw()}<span class="dark">Recalculate</span></div></div>
<div class="vgrid"><div class="vleft"><div class="card"><div class="eyebrow ink">Versions · {len(B["versions"])}</div>{"".join(rows)}</div>
<div class="card"><div class="eyebrow ink">Detected runs · {len(D)}</div>{det}</div></div>
<div class="card"><div class="eyebrow ink">Add version</div><div class="field"><span class="sub">Name <i>(optional)</i></span><div class="inp mono ph">Version name</div></div><div class="field"><span class="sub">Folder</span><div class="inp mono ph">/path/to/version/folder</div></div><span class="dark" style="display:inline-block;margin-top:6px">Add and evaluate</span>
<div class="sub" style="margin-top:14px;font-size:12.5px">Adding a version validates the pairs against {esc(VL(REF))}, then measures {esc(axes_txt)} once.</div></div></div></main>'''
    return f'<div class="win">{rail("versions")}{main}</div>'


# ---------------------------------------------------------------- deck
order_ = [("dataset", slide_dataset), ("item", slide_item), ("compare", slide_compare), ("bench", slide_bench)]
if ADD.get("optimizers") and RUNS:
    order_.append(("runs", slide_runs))
if ADD.get("experiments") and EXP:
    order_.append(("exp", slide_exp))
order_ += [("versions", slide_versions)]
SLIDE.update({k: n for n, (k, _) in enumerate(order_)})
SLIDES = [fn() for _, fn in order_]

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "base.css")).read() + r"""
/* full screen: no presentation frame around the app */
.slide{padding:0}.win{border:none;border-radius:0;box-shadow:none}
.vstrip{display:grid;grid-template-columns:auto 1.1fr .9fr 1.5fr;gap:22px;align-items:center;margin:18px 0 14px;padding:12px 18px;background:var(--card);border:1px solid var(--line);border-radius:16px}
.vstrip .seg{margin:0}.vs{display:contents}.vsn{font-size:14px;margin-bottom:6px}.vsn b{font:600 15px "JetBrains Mono"}
.sbar.wide{max-width:none;height:6px}.bars.mini{height:30px;margin:4px 0 0}.vst{font-size:12.5px;color:var(--ink2);margin-top:4px;line-height:1.5}.vst b{color:var(--ink);font-weight:600}
.otag{color:#2a78d6;cursor:pointer;white-space:nowrap}.otag:hover{text-decoration:underline}
.sbar{display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;max-width:150px}.sbar i{display:block}
.strow{grid-template-columns:44px 54px repeat(var(--n),minmax(0,1fr)) 84px 54px}
.strow .prm{font-size:11px;color:var(--ink2)}
.mcards{grid-template-columns:repeat(3,1fr)}.mhead .pill{margin-left:auto;font-size:11px;padding:2px 8px}
.mxs{display:grid;grid-template-columns:1fr 1fr;gap:18px}.mxg{display:grid;gap:1px;aspect-ratio:1;max-height:190px;background:var(--line)}.mxg i{display:block}
.filmstrip{overflow:hidden;flex-wrap:nowrap}
.scroll .grid{grid-template-columns:repeat(auto-fill,minmax(92px,1fr))}
.strow.sth span{letter-spacing:.07em!important;text-transform:uppercase!important;font-size:10.5px!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.verdict{overflow:auto}
.bars i.stk{display:flex;flex-direction:column;background:none}.bars i.stk b{display:block;width:100%}
.ghead{display:flex;justify-content:space-between;align-items:center;gap:10px}.tsum{font-size:13px;color:var(--ink2);margin:10px 0 2px}.tsum b{font-weight:600}
.ocols2{display:grid;grid-template-columns:1.25fr 1fr;gap:14px;flex:1;min-height:0;margin-top:20px}
.ocright{display:flex;flex-direction:column;gap:14px;min-height:0}
.rkcard{padding:14px 18px;flex:none;max-height:42%;overflow:auto}
.rkrow{display:grid;grid-template-columns:1.6fr .9fr .7fr .7fr .8fr;gap:8px;align-items:center;padding:7px 6px;border-bottom:1px solid #f0ede7;font-size:13px;cursor:pointer;border-radius:8px;transition:background .2s}
.rkrow:hover{background:#f7f5f1}.rkrow.on{background:#f1efe9}.rkrow.rkh{cursor:default;font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink2);background:none}
.rkname{display:flex;align-items:center;gap:8px;font-weight:500}.rkname .key{width:16px;height:4px}.rkbest{font-weight:600}
.spec .run{transition:opacity .25s}.spec.focus .run{opacity:.18}.spec.focus .run.on{opacity:1}
.ocright .stcard{flex:1}
.lessons ul{margin:8px 0 0;padding-left:18px;color:var(--ink2);font-size:13px;line-height:1.5}
"""

JS = r"""
const slides=[...document.querySelectorAll('.slide')];let cur=0;
function count(root){root.querySelectorAll('.count').forEach(el=>{const to=+el.dataset.to;let t0=null;const f=t=>{t0??=t;const p=Math.min(1,(t-t0)/700);el.textContent=Math.round(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f)};requestAnimationFrame(f)})}
function show(i){i=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,k)=>{s.classList.toggle('active',k===i);s.classList.toggle('prev',k<i)});cur=i;
 const s=slides[i];s.querySelectorAll('.spec .line').forEach(p=>{p.style.animation='none';p.getBoundingClientRect();p.style.animation=''});count(s)}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))show(cur+1);if(['ArrowLeft','PageUp'].includes(e.key))show(cur-1)});
document.querySelectorAll('[data-seg],[data-tabs]').forEach(g=>g.addEventListener('click',e=>{const t=e.target.closest('span');if(!t)return;g.querySelectorAll('span').forEach(x=>x.classList.toggle('on',x===t));
 const card=g.parentElement.querySelector('.toolcard');if(t.dataset.t&&card){card.querySelectorAll('.tool').forEach(p=>p.classList.toggle('on',p.dataset.p===t.dataset.t))}}));
document.querySelectorAll('[data-axis]').forEach(g=>g.addEventListener('click',e=>{const t=e.target.closest('span');if(!t)return;g.querySelectorAll('span').forEach(x=>x.classList.toggle('on',x===t));
 const m=g.closest('main');m.querySelectorAll('[data-grp]').forEach(x=>x.hidden=x.dataset.grp!==t.dataset.k);count(m)}));
document.querySelectorAll('[data-cmp]').forEach(g=>g.addEventListener('click',e=>{const t=e.target.closest('span');if(!t)return;g.querySelectorAll('span').forEach(x=>x.classList.toggle('on',x===t));
 g.closest('main').querySelectorAll('.mid').forEach(x=>x.classList.toggle('on',x.dataset.v===t.dataset.v))}));
document.querySelectorAll('[data-pages]').forEach(g=>g.addEventListener('click',e=>{const t=e.target.closest('span[data-go]');if(t)show(+t.dataset.go)}));
document.querySelectorAll('.otag').forEach(t=>t.addEventListener('click',e=>{e.stopPropagation();show(+t.dataset.go)}));
document.querySelectorAll('.rkrow:not(.rkh)').forEach(c=>c.addEventListener('click',()=>{const m=c.closest('main');m.querySelectorAll('.rkrow').forEach(x=>x.classList.toggle('on',x===c));
 m.querySelectorAll('.stbl').forEach(t=>t.hidden=t.dataset.m!==c.dataset.m);document.getElementById('stname').textContent=c.querySelector('.rkname').textContent;
 const sv=m.querySelector('.ocols2 .spec');sv.classList.add('focus');sv.querySelectorAll('.run').forEach(g=>g.classList.toggle('on',g.dataset.m===c.dataset.m))}));
const E=__EXP__,ST=__ST__,TONE=__TONE__;
if(E){
const byX=Object.fromEntries(E.experiments.map(r=>[r.id,r]));const SK=E.scopes.map(s=>s.key);const U=E.objective.unit==='%'?'%':'';
function lineage(id){const out=[];let c=byX[id];const seen=new Set();while(c&&!seen.has(c.id)){seen.add(c.id);out.unshift(c.id);c=byX[c.parent]}return out}
function last(x){const ks=SK.filter(k=>x.scores[k]!=null);return ks.length?x.scores[ks.at(-1)]:null}
function tint(s){return TONE[ST[s].tone]}
function esc(t){const d=document.createElement('div');d.textContent=t??'';return d.innerHTML}
function showX(id){const r=byX[id];const el=document.getElementById('xdetail');if(!r||!el)return;
 document.querySelectorAll('.xi').forEach(x=>x.classList.toggle('on',x.dataset.x===id));
 const [,bg,fg]=tint(r.outcome.status);const lin=lineage(id);
 const sc=E.scopes.filter(s=>r.scores[s.key]!=null);const max=Math.max(1,...sc.map(s=>Math.abs(r.scores[s.key])));
 const bars=sc.length?sc.map((s,i)=>{const v=r.scores[s.key];return `<div class="scope"><b>${v>0?'+':''}${v.toFixed(1)}${U}</b><i style="height:${Math.max(4,Math.abs(v)/max*60)}px;animation-delay:${i*.1}s"></i>${esc(s.label)}</div>`}).join(''):`<div class="reason">No measured score.</div>`;
 const tb=(E.tables||[]).find(t=>t.for===id);
 const side=tb?`<div class="card mtab"><div class="eyebrow ink">${esc(tb.title)}</div><div class="crow sub" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em">${tb.columns.map(c=>`<span>${esc(c)}</span>`).join('')}</div>${tb.rows.map(row=>`<div class="crow">${row.map((c,i)=>i?`<b>${esc(c)}</b>`:`<span>${esc(c)}</span>`).join('')}</div>`).join('')}</div>`
   :`<div class="card"><div class="eyebrow ink">Change</div><div style="margin-top:10px;font-size:15px">${esc(r.change)}</div><div class="reason">Parent: ${esc(r.parent||'—')}</div></div>`;
 el.innerHTML=`<div class="xhead"><h2>${esc(r.id)} · ${esc(r.change)}</h2><span class="pill" style="background:${bg};color:${fg}">${esc(r.outcome.label)}</span>${r.is_best?'<span class="tag">Current best</span>':''}</div>
 <div class="lineage">${lin.map((x,i)=>`${i?'<span>›</span>':''}<span class="ln${x===id?' cur':''}" data-go="${esc(x)}">${esc(x)}</span>`).join('')}</div>
 <div class="xcards"><div class="card"><div class="eyebrow ink">${esc(E.objective.label)} by scope</div><div class="scopes">${bars}</div><div class="reason">${esc(r.note||'')}</div></div>${side}</div>`;
 el.querySelectorAll('.ln[data-go]').forEach(b=>b.addEventListener('click',()=>showX(b.dataset.go)));drawTraj(id)}
function drawTraj(sel){const el=document.getElementById('xtraj');if(!el)return;const W=560,H=190,pl=40,pr=60,pt=12,pb=26;
 const best=E.experiments.find(r=>r.is_best);const ends=[];if(best)ends.push(best.id);
 const on=new Set(best?lineage(best.id):[]);const other=E.experiments.filter(r=>last(r)!=null&&!on.has(r.id)).pop();if(other)ends.push(other.id);
 const paths=ends.map(id=>lineage(id).filter(x=>last(byX[x])!=null));const n=Math.max(2,...paths.map(p=>p.length));
 const vals=E.experiments.map(last).filter(v=>v!=null);const goal=E.objective.goal;
 const raw=(Math.max(...vals,goal??0)*1.1-Math.min(0,...vals))/4||1,e=10**Math.floor(Math.log10(raw)),st=[1,2,2.5,5,10].map(k=>k*e).find(k=>k>=raw);const ymin=Math.floor(Math.min(0,...vals)/st)*st,ymax=Math.ceil(Math.max(...vals,goal??0)*1.1/st)*st;const X=i=>pl+i/(n-1)*(W-pl-pr),Y=v=>pt+(1-(v-ymin)/(ymax-ymin))*(H-pt-pb);
 let g=`<svg class="spec traj" viewBox="0 0 ${W} ${H}">`;for(let v=ymin;v<=ymax+1e-9;v+=st){g+=`<line class="grid" x1="${pl}" x2="${W-pr}" y1="${Y(v)}" y2="${Y(v)}"/><text class="ax" x="${pl-6}" y="${Y(v)+4}" text-anchor="end">${v.toFixed(0)}${U}</text>`}
 if(goal!=null)g+=`<line class="nyq" x1="${pl}" x2="${W-pr}" y1="${Y(goal)}" y2="${Y(goal)}"/><text class="ax" x="${W-pr}" y="${Y(goal)-5}" text-anchor="end">goal ${goal}${U}</text>`;
 const C=["#2a78d6","#eb6834"];paths.forEach((p,k)=>{const pts=p.map((id,i)=>[X(i),Y(last(byX[id])),id]);
  g+=`<path class="line" style="stroke:${C[k]}" d="M${pts.map(q=>q[0]+','+q[1]).join(' L')}"/>`;
  pts.forEach(q=>g+=`<circle class="pt" data-go="${q[2]}" cx="${q[0]}" cy="${q[1]}" r="${q[2]===sel?6:4}" fill="${q[2]===sel?C[k]:'#fffefc'}" stroke="${C[k]}" stroke-width="2"><title>${q[2]} · ${last(byX[q[2]]).toFixed(1)}${U}</title></circle>`);
  const l=pts.at(-1);g+=`<text class="lab" x="${l[0]+10}" y="${l[1]+4}">${l[2]}</text>`});
 el.innerHTML=g+'</svg>';el.querySelectorAll('.pt').forEach(c=>c.addEventListener('click',()=>showX(c.dataset.go)))}
document.querySelectorAll('.xi').forEach(x=>x.addEventListener('click',()=>showX(x.dataset.x)));
(()=>{const b=E.experiments.find(r=>r.is_best)||E.experiments.at(-1);if(b)showX(b.id)})();
}
show(+location.hash.slice(1)||0);addEventListener('hashchange',()=>show(+location.hash.slice(1)||0));
"""
js = JS.replace("__EXP__", json.dumps(EXP if (ADD.get("experiments") and EXP) else None, ensure_ascii=False)).replace("__ST__", json.dumps(ST)).replace("__TONE__", json.dumps(TONE))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(B.get("title", "QC Workbench"))}</title>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="deck">{"".join(f'<section class="slide">{s}</section>' for s in SLIDES)}</div><script>{js}</script></body></html>"""
open(OUT, "w", encoding="utf-8").write(page)
print(OUT, len(page) // 1024, "KB", [k for k, _ in order_])
