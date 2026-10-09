"""Look of the app (J-15 minimal redesign over C-12): CSS and small HTML blocks. Owner: Cristian; built with José.

Pure functions, no Streamlit, so they can be tested. Every value that comes from the data
(headlines, IDs, sources) goes through html.escape: a headline is external text and one of
them is a prompt injection (T07); here it must stay text, never markup.

Monochrome: ink #151515 on #F4F4F2, Archivo for text and IBM Plex Mono for data (both served
from app/static/fonts, so the demo stays offline). Meaning never depends on color: every chip
carries its word, and evidence states also carry a mark that differs in fill (■ ◧ □).
"""

from html import escape

INK = "#151515"
PAPER = "#F4F4F2"
MUTED = "#5E5E5A"
HAIRLINE = "#DCDCD8"

CSS = """
<style>
:root{--ink:#151515;--paper:#F4F4F2;--muted:#5E5E5A;--hair:#DCDCD8}
html,body,.stApp{background:var(--paper)}
[data-testid="stMainMenu"],[data-testid="stAppDeployButton"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"]{display:none!important}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:2.2rem;max-width:1376px}
section[data-testid="stSidebar"]{background:var(--paper);border-right:1px solid var(--ink)}
section[data-testid="stSidebar"] .block-container{padding-top:1.4rem}
/* Buttons and inputs: pills with a 1px ink border; primary is ink on paper inverted. */
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{border-radius:999px;border:1px solid var(--ink);
  background:transparent;color:var(--ink);min-height:44px;padding:0 20px}
.stButton>button:hover,.stFormSubmitButton>button:hover,.stDownloadButton>button:hover{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:var(--ink);color:var(--paper)}
[data-testid="stTextInputRootElement"]{border-radius:999px;border-color:var(--ink);background:transparent;padding:0 8px}
[data-testid="stForm"]{border:0;padding:0}
[data-testid="stAlertContainer"]{background:transparent!important;border:1px solid var(--ink);border-radius:14px;color:var(--ink)!important}
[data-testid="stAlertContainer"] p{font-size:14px;line-height:1.5}
[data-testid="stExpanderIconError"],[data-testid="stExpanderIconCheck"]{color:var(--ink)!important}
.st-key-pitch{gap:0}
.st-key-pitch .stButton>button{justify-content:flex-start;text-align:left;border:0;border-bottom:1px solid var(--hair);border-radius:0;min-height:48px;padding:12px 14px;font-size:15px}
.st-key-pitch .stButton>button:hover{border-radius:14px;border-bottom-color:transparent}
.st-key-pitch .stButton>button>div,.st-key-pitch .stButton>button [data-testid="stMarkdownContainer"]{justify-content:flex-start;width:100%}
.st-key-pitch .stButton>button p{text-align:left;width:100%}
/* Navigation and the inbox list are radios drawn as rows: no circle, the selected row inverts. */
.st-key-vista [data-testid="stRadioOption"]>div>div:first-child,
.st-key-sel_cluster [data-testid="stRadioOption"]>div>div:first-child{display:none}
.st-key-vista [role="radiogroup"],.st-key-sel_cluster [role="radiogroup"]{gap:0;width:100%}
.st-key-vista [role="radiogroup"]>div{width:100%;padding:9px 16px;border-radius:999px;cursor:pointer}
.st-key-vista [role="radiogroup"]>div:hover{background:#EBEBE8}
.st-key-vista [role="radiogroup"]>div[data-selected="true"]{background:var(--ink)}
.st-key-vista [role="radiogroup"]>div[data-selected="true"] *{color:var(--paper)!important}
.st-key-vista [data-testid="stRadioOption"] p{font-size:16px}
.st-key-sel_cluster [role="radiogroup"]>div{width:100%;padding:16px 14px;border-bottom:1px solid var(--hair);cursor:pointer}
.st-key-sel_cluster [role="radiogroup"]>div:hover{background:#EBEBE8}
.st-key-sel_cluster [role="radiogroup"]>div[data-selected="true"]{background:var(--ink);border-radius:14px;border-bottom-color:transparent}
.st-key-sel_cluster [role="radiogroup"]>div[data-selected="true"] *{color:var(--paper)!important}
.st-key-sel_cluster [data-testid="stRadioOption"]{width:100%}
.st-key-sel_cluster [data-testid="stRadioOption"] p{font-size:16px;font-weight:500;line-height:1.3;letter-spacing:-.005em}
.st-key-sel_cluster [data-testid="stRadioCaption"]{padding:6px 0 0;margin:0}
.st-key-sel_cluster [data-testid="stRadioCaption"] p{font-size:13px;line-height:1.4;color:var(--muted);opacity:1}
/* HTML blocks. */
.ctvn-eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.ctvn-brand{font-weight:800;font-size:20px;letter-spacing:-.02em;text-transform:uppercase;line-height:1.1}
.ctvn-brand+.ctvn-eyebrow{margin-top:6px}
.ctvn-header{display:flex;flex-direction:column;gap:6px;padding:14px 0;border-top:1px solid var(--ink);margin-top:10px}
.ctvn-header .ctvn-line{font-size:13px;color:var(--muted)}
.ctvn-chips{display:flex;flex-wrap:wrap;gap:6px 8px}
.ctvn-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:12.5px;border:1px solid var(--hair);color:var(--ink);white-space:nowrap}
.ctvn-chip.offline,.ctvn-chip.online,.ctvn-chip.alto,.ctvn-chip.suficiente{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.ctvn-chip.medio,.ctvn-chip.parcial{border-color:var(--ink)}
.ctvn-chip.bajo{color:var(--muted)}
.ctvn-chip.insuficiente,.ctvn-chip.synthetic{border-style:dashed;border-color:var(--ink)}
.ctvn-dot{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block}
.ctvn-pagehead{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 32px;
  padding-bottom:18px;border-bottom:1px solid var(--ink);margin-bottom:6px}
.ctvn-h1{margin:0;font-weight:700;font-size:clamp(40px,5.2vw,80px);line-height:.95;letter-spacing:-.035em}
.ctvn-stats{margin-left:auto;font-size:14px;line-height:1.6;color:var(--muted);text-align:right}
.ctvn-sec{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  padding-bottom:10px;border-bottom:1px solid var(--ink);margin:30px 0 0}
.ctvn-row{display:flex;flex-direction:column;gap:5px;padding:13px 0;border-bottom:1px solid var(--hair)}
.ctvn-row .ctvn-eyebrow{font-size:10.5px}
.ctvn-check{display:flex;gap:12px;padding:13px 0;border-bottom:1px solid var(--hair)}
.ctvn-check i{flex:none;width:14px;height:14px;margin-top:5px;border:1.5px solid var(--ink)}
.ctvn-cite{font-family:'IBM Plex Mono',monospace;font-size:12px;text-decoration:underline dotted;text-underline-offset:3px;word-break:break-word}
.ctvn-cite.bad{text-decoration-style:solid}
.ctvn-cite small{font-size:11px;color:var(--muted);text-decoration:none;margin-left:8px}
.ctvn-detail{font-size:13px;color:var(--muted)}
.ctvn-more summary{cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:4px 0;list-style-position:inside}
.ctvn-more summary:hover{color:var(--ink)}
.ctvn-more[open] summary{color:var(--ink)}
.ctvn-more>div{padding:5px 0 0}
.st-key-ficha{scroll-margin-top:56px}
.st-key-sel_cluster [data-testid="stRadioCaption"]{cursor:pointer}
.ctvn-load{padding:18vh 0 0;max-width:560px}
.ctvn-ask{margin-top:22px;font-size:15px;color:var(--muted)}
.ctvn-load b{display:block;font-weight:700;font-size:44px;letter-spacing:-.03em;line-height:1}
.ctvn-load p{margin:14px 0 22px;color:var(--muted)}
.ctvn-load i{display:block;height:2px;background:var(--hair);overflow:hidden}
.ctvn-load i u{display:block;width:30%;height:2px;background:var(--ink);animation:ctvn-slide 1.2s cubic-bezier(.16,1,.3,1) infinite}
@keyframes ctvn-slide{from{transform:translateX(-100%)}to{transform:translateX(340%)}}
@media (prefers-reduced-motion: reduce){.ctvn-load i u{animation:none;width:100%}}
.ctvn-muted{color:var(--muted)}
.ctvn-fhead{display:flex;flex-wrap:wrap;align-items:flex-start;gap:20px 40px;margin-top:10px}
.ctvn-fhead h2.ctvn-title{margin:0!important;padding:0!important;flex:1 1 320px;min-width:0;font-weight:600!important;font-size:clamp(24px,2.1vw,32px)!important;line-height:1.12!important;letter-spacing:-.022em}
.ctvn-pagehead h1.ctvn-h1{padding:0!important;font-weight:700!important;font-size:clamp(40px,4.6vw,76px)!important;line-height:.95!important;letter-spacing:-.035em}
.ctvn-header .ctvn-chip{white-space:normal;line-height:1.4}
.ctvn-p{flex:none;text-align:right}
.ctvn-p b{display:block;font-weight:800;font-size:88px;line-height:.85;letter-spacing:-.05em}
.ctvn-p span{display:block;padding-top:10px;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.ctvn-meta{display:flex;flex-wrap:wrap;gap:4px 22px;margin-top:14px;font-size:14px;color:var(--muted)}
.ctvn-meta span:first-child{color:var(--ink);font-weight:500}
.ctvn-proposed{margin-top:10px;color:var(--muted)}
.ctvn-action{border:1px solid var(--ink);border-radius:20px;padding:20px 24px;margin:26px 0 4px;display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline}
.ctvn-action span{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.ctvn-action p{margin:0;font-size:17px}
.ctvn-abst{background:var(--ink);color:var(--paper);border-radius:20px;padding:30px 34px;margin:26px 0 4px;display:flex;flex-direction:column;gap:10px}
.ctvn-abst span{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;opacity:.7}
.ctvn-abst b{font-weight:700;font-size:36px;line-height:1.05;letter-spacing:-.03em}
.ctvn-abst p{margin:0;max-width:64ch;opacity:.9}
.ctvn-score{display:grid;grid-template-columns:minmax(140px,220px) minmax(0,1fr) 150px;align-items:center;gap:18px;padding:11px 0;border-bottom:1px solid var(--hair)}
.ctvn-score i{display:block;height:2px;background:var(--hair)}
.ctvn-score i u{display:block;height:2px;background:var(--ink);text-decoration:none}
.ctvn-score em{font-style:normal;font-family:'IBM Plex Mono',monospace;font-size:13px;text-align:right}
.ctvn-lead{margin:14px 0 0;max-width:66ch;font-size:22px;line-height:1.45;letter-spacing:-.012em}
.ctvn-draft{margin:14px 0 0;max-width:68ch;font-size:19px;line-height:1.55}
.ctvn-contra{border:1px solid var(--ink);border-radius:20px;padding:22px 26px;margin-top:26px}
.ctvn-contra>span{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.ctvn-contra .ctvn-two{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-top:14px}
.ctvn-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0 28px;border-top:1px solid var(--ink)}
.ctvn-tile{padding:14px 0;border-bottom:1px solid var(--hair)}
.ctvn-tile span{display:block;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.ctvn-tile b{display:block;font-weight:700;font-size:30px;letter-spacing:-.03em;line-height:1.2}
.ctvn-tile small{display:block;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}
.ctvn-card{display:grid;grid-template-columns:110px minmax(0,1fr) 250px;gap:20px;align-items:start}
.ctvn-bars{display:flex;flex-direction:column;gap:6px}
.ctvn-bar{display:grid;grid-template-columns:16px minmax(0,1fr) 54px;gap:8px;align-items:center;font-size:13px}
.ctvn-bar i{display:block;height:2px;background:var(--hair)}
.ctvn-bar i u{display:block;height:2px;background:var(--ink);text-decoration:none}
.ctvn-bar em{font-style:normal;text-align:right;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.ctvn-type{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
@media (max-width: 900px){.ctvn-card{grid-template-columns:1fr}.ctvn-score{grid-template-columns:1fr 110px}.ctvn-score i{display:none}
  .ctvn-p b{font-size:64px}.ctvn-stats{text-align:left}}
</style>
"""

BAND_CLASS = {"alto": "alto", "medio": "medio", "bajo": "bajo"}
EVIDENCE_CLASS = {"suficiente para el borrador": "suficiente", "parcial": "parcial", "insuficiente": "insuficiente"}
EVIDENCE_MARK = {"suficiente para el borrador": "■", "parcial": "◧", "insuficiente": "□"}
COMPONENT_KEYS = ["R", "I", "U", "N", "E"]
_MD_SPECIAL = "\\`*_{}[]()#+-.!|<>~"


def md_escape(text) -> str:
    """Widget labels are Markdown: external text must not turn into formatting or links."""
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in str(text))


def evidence_mark(estado: str | None) -> str:
    return EVIDENCE_MARK.get(estado, "·")


def chip(text: str, kind: str = "") -> str:
    return f'<span class="ctvn-chip {escape(kind)}">{escape(str(text))}</span>'


def band_chip(rango: str | None) -> str:
    return chip(f"P {rango or '—'}", BAND_CLASS.get(rango, ""))


def evidence_chip(estado: str | None) -> str:
    return chip(f"Evidencia: {estado or '—'}", EVIDENCE_CLASS.get(estado, ""))


def header_html(offline: bool, data_label: str, n_news: int, n_events: int, cut: str | None,
                synthetic: bool) -> str:
    """Sidebar state block in product words: connection mode, corpus size, data date. No paths or flags."""
    mode = ('<span class="ctvn-chip offline"><span class="ctvn-dot"></span>Sin internet · respuestas guardadas</span>'
            if offline else '<span class="ctvn-chip online"><span class="ctvn-dot"></span>En línea</span>')
    lines = [f'<div class="ctvn-line">{n_news:,} noticias · {n_events:,} eventos</div>']
    if cut:
        lines.append(f'<div class="ctvn-line">Datos al {escape(cut)}</div>')
    if synthetic:
        lines.append(chip("Incluye noticias sintéticas de prueba", "synthetic"))
    return f'<div class="ctvn-header"><div class="ctvn-chips">{mode}</div>{"".join(lines)}</div>'


def brand_html() -> str:
    return ('<div class="ctvn-brand">Copiloto TVN</div>'
            '<div class="ctvn-eyebrow">Borradores para tu revisión</div>')


def loading_html(title: str, text: str) -> str:
    """First load: a visible, branded wait (an ink bar), never the framework's own spinner text."""
    return f'<div class="ctvn-load" role="status" aria-live="polite"><b>{escape(title)}</b><p>{escape(text)}</p><i><u></u></i></div>'


def page_head_html(title: str, stats: list[str]) -> str:
    """Big page title with its mono facts on the right."""
    return (f'<div class="ctvn-pagehead"><h1 class="ctvn-h1">{escape(title)}</h1>'
            f'<div class="ctvn-stats">{"<br>".join(escape(s) for s in stats)}</div></div>')


def section_html(label: str) -> str:
    return f'<div class="ctvn-sec">{escape(label)}</div>'


def ficha_head_html(eyebrow: str, titular: str, p: float, p_note: str, meta: list[str],
                    proposed: str | None = None) -> str:
    """Case header: the real headline and its priority as the protagonist, then the facts in plain words."""
    head = (f'<div class="ctvn-eyebrow">{escape(eyebrow)}</div>'
            f'<div class="ctvn-fhead"><h2 class="ctvn-title">{escape(titular)}</h2>'
            f'<div class="ctvn-p"><b>{float(p):.1f}</b><span>{escape(p_note)}</span></div></div>'
            f'<div class="ctvn-meta">{"".join(f"<span>{escape(m)}</span>" for m in meta if m)}</div>')
    if proposed:
        head += f'<div class="ctvn-proposed"><em>Título sugerido por la IA, para revisar:</em> {escape(proposed)}</div>'
    return head


def action_html(text: str) -> str:
    return f'<div class="ctvn-action"><span>Acción recomendada</span><p>{escape(text)}</p></div>'


def alert_html(text: str, tag: str = "Aviso de seguridad") -> str:
    """A source that tried to give instructions: outlined, never hidden."""
    return f'<div class="ctvn-action"><span>{escape(tag)}</span><p>{escape(text)}</p></div>'


def abstention_html(title: str, text: str, tag: str = "Sin respuesta") -> str:
    """Absence shown as clearly as evidence: the system did not answer, and why."""
    return f'<div class="ctvn-abst" role="status"><span>{escape(tag)}</span><b>{escape(title)}</b><p>{escape(text)}</p></div>'


def _cite_html(c: dict) -> str:
    mark = {True: "✓ ", False: "✗ no aparece en la fuente · "}.get(c.get("found"), "")
    context = f' <span class="ctvn-muted">· {escape(c["context"])}</span>' if c.get("context") else ""
    bad = " bad" if c.get("found") is False else ""
    ident = f'<small>{escape(c["ident"])}</small>' if c.get("ident") else ""
    return f'<span class="ctvn-cite{bad}">{escape(mark + c["label"])}{ident}</span>{context}'


def claim_html(kind_label: str, text: str, cites: list[dict], more_label: str | None = None) -> str:
    """One claim with its type and every citation: the source in words first, its ID (the challenge's
    citation key) small beside it. A cite: label, ident, found (bool or None), context.

    With `more_label`, only the first citation stays visible and the rest fold under a native
    <details> ('Ver las N fuentes'), so a well-sourced claim does not bury the case card.
    """
    parts = [f'<span class="ctvn-type">{escape(kind_label)}</span>', f"<span>{escape(text)}</span>"]
    shown = cites[:1] if more_label and len(cites) > 1 else cites
    parts += [_cite_html(c) for c in shown]
    if len(shown) < len(cites):
        rest = "".join(f'<div>{_cite_html(c)}</div>' for c in cites[1:])
        parts.append(f'<details class="ctvn-more"><summary>{escape(more_label)}</summary>{rest}</details>')
    return f'<div class="ctvn-row">{"".join(parts)}</div>'


def check_html(text: str) -> str:
    """A pending verification: an empty box, as visible as what is backed."""
    return f'<div class="ctvn-check"><i aria-hidden="true"></i><span>{escape(text)}</span></div>'


def note_html(text: str) -> str:
    return f'<div class="ctvn-row ctvn-muted">{escape(text)}</div>'


def score_html(points: list[dict]) -> str:
    """Each component as a thin bar and the points it adds ('30.0 de 30'); a missing value says 'sin dato'."""
    rows = []
    for p in points:
        label = p["nombre"]
        if p["valor"] is None:
            rows.append(f'<div class="ctvn-score"><span>{escape(label)}</span><i></i><em>sin dato</em></div>')
        else:
            width = max(0.0, min(1.0, p["valor"])) * 100
            rows.append(f'<div class="ctvn-score"><span>{escape(label)}</span><i><u style="width:{width:.0f}%"></u></i>'
                        f'<em>{p["puntos"]:.1f} de {p["peso"]}</em></div>')
    return "".join(rows)


def contradictions_html(items: list[dict], labels) -> str:
    """T05: both versions side by side, each with its citation; never resolved by the app."""
    blocks = []
    for c in items:
        sides = "".join(
            f'<div><div>{escape(str(c.get(f"version_{s}") or "—"))}</div>'
            f'<div class="ctvn-cite">{escape(labels(c.get(f"cita_{s}")))}</div></div>' for s in ("a", "b"))
        blocks.append(f'<div class="ctvn-contra"><span>Las fuentes no coinciden · no elijo una versión: verifica ambas</span>'
                      f'<div class="ctvn-two">{sides}</div></div>')
    return "".join(blocks)


def lead_html(text: str, cls: str = "ctvn-lead") -> str:
    return f'<p class="{cls}">{escape(text)}</p>'


def tiles_html(tiles: list[tuple[str, str, str]]) -> str:
    """(label, value, note) boxes; value is already formatted, never a filled-in 0 for a null."""
    return '<div class="ctvn-tiles">' + "".join(
        f'<div class="ctvn-tile"><span>{escape(label)}</span><b>{escape(value)}</b>'
        + (f' <small>{escape(note)}</small>' if note else "") + "</div>"
        for label, value, note in tiles) + "</div>"


def bars_html(values: dict) -> str:
    """R..E as bars; a missing component shows 'sin dato', never an empty bar."""
    rows = []
    for k in COMPONENT_KEYS:
        v = values.get(k)
        if v is None or v != v:  # None or NaN
            rows.append(f'<div class="ctvn-bar"><b>{k}</b><i></i><em>sin dato</em></div>')
        else:
            rows.append(f'<div class="ctvn-bar"><b>{k}</b><i><u style="width:{max(0.0, min(1.0, float(v))) * 100:.0f}%">'
                        f'</u></i><em>{float(v):.2f}</em></div>')
    return '<div class="ctvn-bars">' + "".join(rows) + "</div>"


def event_card_html(pos, p, rango, tema, estado, titular, meta, id_titular, components: dict,
                    marks: str = "") -> str:
    """One prioritized event: rank and P, chips, the real headline with its ID, and R..E."""
    extra = f' {chip(marks)}' if marks else ""
    return (f'<div class="ctvn-card"><div class="ctvn-rank"><span>#{escape(str(pos))}</span>'
            f'<b>{float(p):.1f}</b>{band_chip(rango)}</div>'
            f'<div class="ctvn-main"><div class="ctvn-chips">{chip(tema or "— (sin dato)")}{evidence_chip(estado)}{extra}</div>'
            f'<p class="ctvn-title">{escape(titular or "— (sin titular)")}</p>'
            f'<p class="ctvn-meta">{escape(meta)} · <span class="ctvn-mono">{escape(id_titular or "—")} · titulo</span></p>'
            f'</div>{bars_html(components)}</div>')


def claim_type_chip(kind: str, label: str) -> str:
    return f'<span class="ctvn-type {escape(kind)}">{escape(label)}</span>'


def busy_css(container_key: str, keep_key: str) -> str:
    """While a draft is being written, dim the rest of the case card; the running steps stay sharp."""
    return (f"<style>.st-key-{container_key}>*:not(.st-key-{keep_key}):not(:has(.st-key-{keep_key}))"
            "{opacity:.35;pointer-events:none;transition:opacity .2s}</style>")


def scroll_js(selector: str, max_width: int = 640) -> str:
    """Brings the case card into view on a phone after an event is picked (columns stack under
    640 px, so the card sits below the list). Wider screens show both side by side: no jump."""
    return (f"<script>(function(){{if(window.innerWidth>{max_width})return;"
            f"var n=0,t=setInterval(function(){{var el=document.querySelector({selector!r});"
            f"if(el){{el.scrollIntoView({{behavior:'smooth',block:'start'}});clearInterval(t);}}"
            f"if(++n>40)clearInterval(t);}},50);}})();</script>")


# The list's grey caption sits outside the radio's label, so a tap on it selected nothing (half
# of each row on a phone). One document-level listener forwards it to its own row's label.
CAPTION_CLICK_JS = (
    "<script>(function(){if(window.__ctvnCaptionClick)return;window.__ctvnCaptionClick=true;"
    "document.addEventListener('click',function(e){var cap=e.target.closest"
    "('.st-key-sel_cluster [data-testid=\"stRadioCaption\"]');if(!cap)return;"
    "var row=cap.closest('[role=\"radiogroup\"] > *');"
    "var label=row&&(row.tagName==='LABEL'?null:row.querySelector('label'));"
    "if(label)label.click();});})();</script>")
