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
[data-testid="stAlertContainer"] p{font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.04em}
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
.st-key-sel_cluster [data-testid="stRadioCaption"] p{font-family:'IBM Plex Mono',monospace;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--muted);opacity:1}
/* HTML blocks. */
.ctvn-eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.ctvn-brand{font-weight:800;font-size:20px;letter-spacing:-.02em;text-transform:uppercase;line-height:1.1}
.ctvn-brand+.ctvn-eyebrow{margin-top:6px}
.ctvn-header{display:flex;flex-direction:column;gap:6px;padding:14px 0;border-top:1px solid var(--ink);margin-top:10px}
.ctvn-header .ctvn-line{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.ctvn-chips{display:flex;flex-wrap:wrap;gap:6px 8px}
.ctvn-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-family:'IBM Plex Mono',monospace;
  font-size:11px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--hair);color:var(--ink);white-space:nowrap}
.ctvn-chip.offline,.ctvn-chip.online,.ctvn-chip.alto,.ctvn-chip.suficiente{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.ctvn-chip.medio,.ctvn-chip.parcial{border-color:var(--ink)}
.ctvn-chip.bajo{color:var(--muted)}
.ctvn-chip.insuficiente,.ctvn-chip.synthetic{border-style:dashed;border-color:var(--ink)}
.ctvn-dot{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block}
.ctvn-pagehead{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 32px;
  padding-bottom:18px;border-bottom:1px solid var(--ink);margin-bottom:6px}
.ctvn-h1{margin:0;font-weight:700;font-size:clamp(40px,5.2vw,80px);line-height:.95;letter-spacing:-.035em}
.ctvn-stats{margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:12px;line-height:1.7;color:var(--muted);text-align:right}
.ctvn-sec{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  padding-bottom:10px;border-bottom:1px solid var(--ink);margin:30px 0 0}
.ctvn-row{display:flex;flex-direction:column;gap:5px;padding:13px 0;border-bottom:1px solid var(--hair)}
.ctvn-row .ctvn-eyebrow{font-size:10.5px}
.ctvn-check{display:flex;gap:12px;padding:13px 0;border-bottom:1px solid var(--hair)}
.ctvn-check i{flex:none;width:14px;height:14px;margin-top:5px;border:1.5px solid var(--ink)}
.ctvn-cite{font-family:'IBM Plex Mono',monospace;font-size:12px;text-decoration:underline dotted;text-underline-offset:3px;word-break:break-word}
.ctvn-cite.bad{text-decoration-style:solid}
.ctvn-muted{color:var(--muted)}
.ctvn-fhead{display:flex;flex-wrap:wrap;align-items:flex-start;gap:20px 40px;margin-top:10px}
.ctvn-fhead h2.ctvn-title{margin:0!important;padding:0!important;flex:1 1 320px;min-width:0;font-weight:600!important;font-size:clamp(24px,2.1vw,32px)!important;line-height:1.12!important;letter-spacing:-.022em}
.ctvn-pagehead h1.ctvn-h1{padding:0!important;font-weight:700!important;font-size:clamp(40px,4.6vw,76px)!important;line-height:.95!important;letter-spacing:-.035em}
.ctvn-header .ctvn-chip{white-space:normal;line-height:1.4}
.ctvn-p{flex:none;text-align:right}
.ctvn-p b{display:block;font-weight:800;font-size:88px;line-height:.85;letter-spacing:-.05em}
.ctvn-p span{display:block;padding-top:10px;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.ctvn-meta{display:flex;flex-wrap:wrap;gap:6px 22px;margin-top:16px;font-family:'IBM Plex Mono',monospace;font-size:12px;
  letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.ctvn-meta span:first-child{color:var(--ink)}
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
    """Sidebar state block: the mode, data cut and corpus the editor must always see."""
    mode = ('<span class="ctvn-chip offline"><span class="ctvn-dot"></span>Sin internet (OFFLINE=1) · '
            'respuestas desde caché</span>' if offline else
            '<span class="ctvn-chip online"><span class="ctvn-dot"></span>En línea · caché primero</span>')
    lines = [f'<div class="ctvn-line">{n_news:,} noticias · {n_events:,} eventos</div>']
    if cut:
        lines.append(f'<div class="ctvn-line">Corte {escape(cut)}</div>')
    lines.append(f'<div class="ctvn-line">Datos: {escape(data_label)}</div>')
    if synthetic:
        lines.append(chip("Contiene noticias sintéticas (sintetico=true)", "synthetic"))
    return f'<div class="ctvn-header"><div class="ctvn-chips">{mode}</div>{"".join(lines)}</div>'


def brand_html() -> str:
    return ('<div class="ctvn-brand">Copiloto TVN</div>'
            '<div class="ctvn-eyebrow">Nada se publica desde aquí</div>')


def page_head_html(title: str, stats: list[str]) -> str:
    """Big page title with its mono facts on the right."""
    return (f'<div class="ctvn-pagehead"><h1 class="ctvn-h1">{escape(title)}</h1>'
            f'<div class="ctvn-stats">{"<br>".join(escape(s) for s in stats)}</div></div>')


def section_html(label: str) -> str:
    return f'<div class="ctvn-sec">{escape(label)}</div>'


def ficha_head_html(eyebrow: str, titular: str, p: float, rango: str | None, meta: list[str],
                    proposed: str | None = None) -> str:
    """Case header: the real headline and P as the protagonist, then the facts in mono."""
    head = (f'<div class="ctvn-eyebrow">// {escape(eyebrow)}</div>'
            f'<div class="ctvn-fhead"><h2 class="ctvn-title">{escape(titular)}</h2>'
            f'<div class="ctvn-p"><b>{float(p):.1f}</b><span>P · rango {escape(rango or "—")}</span></div></div>'
            f'<div class="ctvn-meta">{"".join(f"<span>{escape(m)}</span>" for m in meta if m)}</div>')
    if proposed:
        head += f'<div class="ctvn-proposed"><em>Título propuesto (generado, para revisión):</em> {escape(proposed)}</div>'
    return head


def action_html(text: str) -> str:
    return f'<div class="ctvn-action"><span>Acción recomendada</span><p>{escape(text)}</p></div>'


def alert_html(text: str, tag: str = "T07 · alerta") -> str:
    """A source that tried to give instructions: outlined, never hidden."""
    return f'<div class="ctvn-action"><span>{escape(tag)}</span><p>{escape(text)}</p></div>'


def abstention_html(title: str, text: str, tag: str = "T06 · abstención") -> str:
    """Absence shown as clearly as evidence: the system did not answer, and why."""
    return f'<div class="ctvn-abst" role="status"><span>{escape(tag)}</span><b>{escape(title)}</b><p>{escape(text)}</p></div>'


def claim_html(kind_label: str, text: str, cites: list[dict]) -> str:
    """One claim with its type and every citation. A cite: label, found (bool or None), context."""
    parts = [f'<span class="ctvn-type">{escape(kind_label)}</span>', f"<span>{escape(text)}</span>"]
    for c in cites:
        mark = {True: "✓ ", False: "✗ no encontrada · "}.get(c.get("found"), "")
        context = f' <span class="ctvn-muted">· {escape(c["context"])}</span>' if c.get("context") else ""
        bad = " bad" if c.get("found") is False else ""
        parts.append(f'<span class="ctvn-cite{bad}">{escape(mark + c["label"])}</span>{context}')
    return f'<div class="ctvn-row">{"".join(parts)}</div>'


def check_html(text: str) -> str:
    """A pending verification: an empty box, as visible as what is backed."""
    return f'<div class="ctvn-check"><i aria-hidden="true"></i><span>{escape(text)}</span></div>'


def note_html(text: str) -> str:
    return f'<div class="ctvn-row ctvn-muted">{escape(text)}</div>'


def score_html(points: list[dict]) -> str:
    """R..E as thin bars with value × weight = points; a missing value says 'sin dato'."""
    rows = []
    for p in points:
        label = f'{p["clave"]} · {p["nombre"]}'
        if p["valor"] is None:
            rows.append(f'<div class="ctvn-score"><span>{escape(label)}</span><i></i><em>sin dato</em></div>')
        else:
            width = max(0.0, min(1.0, p["valor"])) * 100
            rows.append(f'<div class="ctvn-score"><span>{escape(label)}</span><i><u style="width:{width:.0f}%"></u></i>'
                        f'<em>{p["valor"]:.2f} × {p["peso"]} = {p["puntos"]:.1f}</em></div>')
    return "".join(rows)


def contradictions_html(items: list[dict], labels) -> str:
    """T05: both versions side by side, each with its citation; never resolved by the app."""
    blocks = []
    for c in items:
        sides = "".join(
            f'<div><div>{escape(str(c.get(f"version_{s}") or "—"))}</div>'
            f'<div class="ctvn-cite">{escape(labels(c.get(f"cita_{s}")))}</div></div>' for s in ("a", "b"))
        blocks.append(f'<div class="ctvn-contra"><span>T05 · contradicción · no se elige una versión</span>'
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
