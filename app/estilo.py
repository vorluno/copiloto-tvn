"""Editorial look (C-12 redesign): CSS and small HTML blocks. Owner: Cristian; built with José.

Pure functions, no Streamlit, so they can be tested. Every value that comes from the data
(headlines, IDs, sources) goes through html.escape: a headline is external text and one of
them is a prompt injection (T07); here it must stay text, never markup.

Colors: band (alto, medio, bajo) and evidence state each differ in lightness as well as hue,
and every chip carries its word, so meaning never depends on color alone.
"""

from html import escape

CSS = """
<style>
.ctvn-header{background:#FFFFFF;border:1px solid #E3E1DA;border-radius:12px;padding:18px 22px;
  display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}
.ctvn-brand{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px}
.ctvn-brand b{font-family:'Source Serif 4',Georgia,serif;font-size:28px;font-weight:600;letter-spacing:-.01em}
.ctvn-brand span{color:#4A505C;font-size:14px}
.ctvn-chips{display:flex;flex-wrap:wrap;gap:8px}
.ctvn-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:13px;
  font-weight:500;border:1px solid #E3E1DA;background:#F1F0EC;color:#3F444E;white-space:nowrap}
.ctvn-chip.offline{background:#FFF6DF;color:#7A4A00;border-color:#F1D79A}
.ctvn-chip.online{background:#E8F6EE;color:#0E5A33;border-color:#A9DCC0}
.ctvn-chip.synthetic{background:#F2EEFB;color:#4B2E91;border-color:#D5C9F0}
.ctvn-chip.alto{background:#FFF1E6;color:#9A3412;border-color:#F7C9A6}
.ctvn-chip.medio{background:#EEF3FF;color:#163B91;border-color:#C7D5F5}
.ctvn-chip.bajo{background:#F1F0EC;color:#4A505C;border-color:#E3E1DA}
.ctvn-chip.suficiente{background:#E8F6EE;color:#0E5A33;border-color:#A9DCC0}
.ctvn-chip.parcial{background:#FFF6DF;color:#7A4A00;border-color:#F1D79A}
.ctvn-chip.insuficiente{background:#FDEDEB;color:#8A1F17;border-color:#F3B8B1}
.ctvn-dot{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block}
.ctvn-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:4px 0 8px}
.ctvn-tile{background:#FFFFFF;border:1px solid #E3E1DA;border-radius:10px;padding:14px 16px}
.ctvn-tile span{display:block;font-size:13px;color:#4A505C}
.ctvn-tile b{font-family:'Source Serif 4',Georgia,serif;font-size:28px;font-weight:600}
.ctvn-tile small{font-size:13px;color:#4A505C}
.ctvn-card{display:grid;grid-template-columns:110px minmax(0,1fr) 250px;gap:20px;align-items:start}
.ctvn-rank{display:flex;flex-direction:column;gap:6px}
.ctvn-rank span{font-size:13px;color:#4A505C;font-family:'IBM Plex Mono',Menlo,monospace}
.ctvn-rank b{font-family:'Source Serif 4',Georgia,serif;font-size:38px;font-weight:600;line-height:1}
.ctvn-main{display:flex;flex-direction:column;gap:8px;min-width:0}
.ctvn-title{margin:0;font-family:'Source Serif 4',Georgia,serif;font-size:21px;font-weight:600;line-height:1.3}
.ctvn-meta{margin:0;font-size:14px;color:#4A505C}
.ctvn-mono{font-family:'IBM Plex Mono',Menlo,monospace;font-size:13px}
.ctvn-bars{display:flex;flex-direction:column;gap:6px}
.ctvn-bar{display:grid;grid-template-columns:16px minmax(0,1fr) 38px;gap:8px;align-items:center;font-size:13px}
.ctvn-bar i{display:block;height:8px;border-radius:4px;background:#EEECE6;overflow:hidden}
.ctvn-bar i u{display:block;height:100%;background:#1E4FC2;border-radius:4px;text-decoration:none}
.ctvn-bar em{font-style:normal;text-align:right;color:#4A505C;font-family:'IBM Plex Mono',Menlo,monospace}
.ctvn-headline{margin:6px 0 2px;font-family:'Source Serif 4',Georgia,serif;font-size:32px;font-weight:600;
  letter-spacing:-.015em;line-height:1.2}
.ctvn-type{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.ctvn-type.hecho{background:#E8F0FE;color:#163B91}
.ctvn-type.declaracion{background:#F2EEFB;color:#4B2E91}
.ctvn-type.inferencia{background:#FFF6DF;color:#7A4A00}
.ctvn-type.hipotesis{background:#F1F0EC;color:#3F444E}
@media (max-width: 900px){.ctvn-card{grid-template-columns:1fr}}
</style>
"""

BAND_CLASS = {"alto": "alto", "medio": "medio", "bajo": "bajo"}
EVIDENCE_CLASS = {"suficiente para el borrador": "suficiente", "parcial": "parcial", "insuficiente": "insuficiente"}
COMPONENT_KEYS = ["R", "I", "U", "N", "E"]


def chip(text: str, kind: str = "") -> str:
    return f'<span class="ctvn-chip {escape(kind)}">{escape(str(text))}</span>'


def band_chip(rango: str | None) -> str:
    return chip(f"P {rango or '—'}", BAND_CLASS.get(rango, ""))


def evidence_chip(estado: str | None) -> str:
    return chip(f"Evidencia: {estado or '—'}", EVIDENCE_CLASS.get(estado, ""))


def header_html(offline: bool, data_label: str, n_news: int, n_events: int, cut: str | None,
                synthetic: bool) -> str:
    """Top bar: product, the human-review promise, and the state the editor must always see."""
    mode = ('<span class="ctvn-chip offline"><span class="ctvn-dot"></span>Sin internet (OFFLINE=1) · '
            'respuestas desde caché</span>' if offline else
            '<span class="ctvn-chip online"><span class="ctvn-dot"></span>En línea · cada respuesta se guarda '
            'en caché</span>')
    chips = [mode]
    if cut:
        chips.append(chip(f"Corte {cut}"))
    chips.append(chip(f"{n_news:,} noticias · {n_events:,} eventos"))
    chips.append(chip(f"Datos: {data_label}"))
    if synthetic:
        chips.append(chip("Contiene noticias sintéticas (sintetico=true)", "synthetic"))
    return ('<div class="ctvn-header"><div class="ctvn-brand"><b>Copiloto TVN</b>'
            '<span>Borradores para revisión humana. Nada se publica desde aquí.</span></div>'
            f'<div class="ctvn-chips">{"".join(chips)}</div></div>')


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
