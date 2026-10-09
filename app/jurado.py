"""Fuentes y datos blocks for the jury (J-16): the priority rules with a weights simulator and the
live challenge check. Owner: Cristian; built with José.

Streamlit rendering only; the logic lives in app/simulador.py and app/pruebas_vivo.py, the words
in app/textos.py and the look reuses app/estilo.py (monochrome, Archivo + IBM Plex Mono).
"""

from html import escape

import pandas as pd
import streamlit as st

from app import pruebas_vivo as pv
from app import simulador as sim
from app import textos as tx
from app.estilo import alert_html, note_html, section_html, tiles_html

KEYS = {k: f"sim_{k}" for k in sim.COMPONENTS}

EXTRA_CSS = """
<style>
#ctvn-respuesta,#ctvn-progreso{scroll-margin-top:64px}
.ctvn-near{margin:0!important;padding:22px 0 4px;font-size:17px}
.ctvn-unverified{border-style:dashed}
.ctvn-test{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 24px;align-items:baseline;padding:13px 0;border-bottom:1px solid var(--hair)}
.ctvn-test b{font-weight:600}
.ctvn-test .ctvn-detail{grid-column:1}
.ctvn-test em{grid-column:2;grid-row:1 / span 2;font-style:normal;font-family:'IBM Plex Mono',monospace;font-size:13px;text-align:right;white-space:nowrap}
.ctvn-test em.fail{background:var(--ink);color:var(--paper);padding:2px 10px;border-radius:999px}
.ctvn-test em.model{color:var(--muted)}
.ctvn-test .ctvn-model{grid-column:1 / -1;font-family:'IBM Plex Mono',monospace;font-size:12px}
.ctvn-sim{display:grid;grid-template-columns:36px 64px minmax(0,1fr) 110px 180px;gap:4px 14px;align-items:baseline;padding:11px 0;border-bottom:1px solid var(--hair);font-size:15px}
.ctvn-sim b{font-weight:700;font-family:'IBM Plex Mono',monospace}
.ctvn-sim em{font-style:normal;font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--muted)}
.ctvn-sim em.up,.ctvn-sim em.down{color:var(--ink);font-weight:600}
.ctvn-sim .n{font-family:'IBM Plex Mono',monospace;font-size:13px;text-align:right}
.ctvn-sim .o{color:var(--muted)}
.ctvn-sim .lbl{display:none;font-style:normal}
.ctvn-sim-head{border-bottom:1px solid var(--ink);margin-top:14px}
.ctvn-sim-head span{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.ctvn-sim-head span:nth-child(n+4){text-align:right}
.ctvn-rule{font-size:15px;line-height:1.6;margin:14px 0 0;max-width:72ch}
@media (max-width: 640px){.ctvn-sim{grid-template-columns:28px 52px minmax(0,1fr)}
  .ctvn-sim .n{grid-column:3;text-align:left}.ctvn-sim .lbl{display:inline}.ctvn-sim-head span:nth-child(n+4){display:none}
  .ctvn-test{grid-template-columns:1fr}.ctvn-test em{grid-column:1;grid-row:auto;text-align:left}
}
</style>
"""


def _reset_weights(rules: dict) -> None:
    for k, key in KEYS.items():
        st.session_state[key] = int(rules["pesos"][k])


def _range_text(rules: dict) -> str:
    parts = []
    for name in ("alto", "medio", "bajo"):
        low, high, inclusive = rules["_ranges"][name]
        upper = f"{high:g}" if inclusive else f"menos de {high:g}"
        parts.append(f"{tx.RANGO_NOMBRE[name]}: de {low:g} a {upper}")
    return " · ".join(parts)


def render_rules(rules: dict) -> None:
    """The official rules as the jury reads them: version, the five weights and the ranges."""
    st.markdown(section_html("Reglas de prioridad"), unsafe_allow_html=True)
    formula = " + ".join(f"{rules['pesos'][k]} × {tx.COMPONENTE[k].lower()}" for k in sim.COMPONENTS)
    st.markdown(f'<p class="ctvn-rule">Versión de reglas <b>{escape(str(rules["version"]))}</b>. '
                f'Prioridad = {escape(formula)}. Cada parte va de 0 a 1 y la calculan reglas fijas, no la IA.</p>',
                unsafe_allow_html=True)
    st.markdown(tiles_html([(tx.COMPONENTE[k], f"{rules['pesos'][k]}", "de 100") for k in sim.COMPONENTS]),
                unsafe_allow_html=True)
    st.caption(f"Rangos de prioridad · {_range_text(rules)}. Una prioridad alta no autoriza a publicar.")


@st.fragment
def render_simulator(scored: pd.DataFrame, titles: dict, rules: dict) -> None:
    """Five weights normalized to 100; the top 10 recomputed from the components already scored."""
    st.markdown(section_html("¿Y si los pesos fueran otros?"), unsafe_allow_html=True)
    st.markdown(alert_html(tx.SIMULACION_AVISO, "Simulación"), unsafe_allow_html=True)
    for k, key in KEYS.items():
        st.session_state.setdefault(key, int(rules["pesos"][k]))
    cols = st.columns(len(KEYS))
    for col, (k, key) in zip(cols, KEYS.items()):
        col.slider(tx.COMPONENTE[k], min_value=0, max_value=100, step=5, key=key)
    weights = {k: st.session_state[key] for k, key in KEYS.items()}
    norm = sim.normalize(weights)
    official = sim.is_official(weights, rules)
    left, right = st.columns([2, 1], vertical_alignment="center")
    left.markdown(note_html("Pesos que se usan, llevados a 100: " + " · ".join(
        f"{tx.COMPONENTE[k]} {norm[k]:.1f}" for k in sim.COMPONENTS)), unsafe_allow_html=True)
    right.button("Volver a los pesos oficiales", on_click=_reset_weights, args=(rules,), width="stretch",
                 disabled=official, key="sim_reset")

    simulated = sim.simulate(scored, weights, rules)
    if simulated.empty:
        st.markdown(note_html("Todavía no hay eventos para ordenar."), unsafe_allow_html=True)
        return
    head = sim.top(simulated)
    st.markdown(_top_html(head, titles), unsafe_allow_html=True)
    if official:
        st.caption("Con los pesos oficiales el orden es el mismo de la Mesa.")
    else:
        out = sim.left_top(simulated)
        moved = int((head["cambio"] != 0).sum())
        lines = [f"{moved} de los 10 primeros cambian de puesto."]
        if not out.empty:
            lines.append("Salen del top 10: " + "; ".join(
                f"{tx.limpiar_titular(titles.get(r.cluster_id))} (del n.º {int(r.posicion_oficial)} al n.º {int(r.posicion)})"
                for r in out.itertuples()) + ".")
        st.caption(" ".join(lines))


def _top_html(head: pd.DataFrame, titles: dict) -> str:
    """Simulated top 10 against the official order: place, move, headline, simulated and official priority."""
    rows = ['<div class="ctvn-sim ctvn-sim-head"><span>N.º</span><span>Cambio</span><span>Titular</span>'
            '<span>Simulada</span><span>Oficial</span></div>']
    for r in head.itertuples():
        moved = tx.puestos(r.cambio)
        rows.append(
            f'<div class="ctvn-sim"><b>{int(r.posicion)}</b><em class="{"up" if r.cambio > 0 else "down" if r.cambio < 0 else ""}">'
            f'{escape(moved)}</em><span class="t">{escape(tx.limpiar_titular(titles.get(r.cluster_id)))}</span>'
            f'<span class="n"><i class="lbl">Simulada: </i>{r.P:.1f} · {escape(tx.RANGO_NOMBRE.get(r.rango, "—"))}</span>'
            f'<span class="n o"><i class="lbl">Oficial: </i>n.º {int(r.posicion_oficial)} · {r.P_oficial:.1f} · '
            f'{escape(tx.RANGO_NOMBRE.get(r.rango_oficial, "—"))}</span></div>')
    return "".join(rows)


def _model_note(record: dict | None) -> str:
    text = "Se corre con el modelo de embeddings, que este servidor no trae"
    if not record or not record.get("fecha"):
        return text + ". Sin corrida registrada."
    text += f". Última corrida: {tx.fecha(record['fecha'] + 'T12:00:00Z', con_hora=False)}"
    if record.get("estado") and record.get("de"):
        text += f", {'pasó' if record['estado'] == 'pasa' else 'no pasó'} {record['pasaron']} de {record['de']}"
    return text + "."


def _test_rows(run: "pv.LiveRun | None") -> str:
    recorded = pv.last_recorded()
    rows = []
    for test_id in pv.ALL_IDS:
        name, checks = tx.PRUEBA_RETO[test_id]
        note = ""
        if test_id in pv.MODEL_TESTS:
            result, cls = "Se corre aparte", "model"
            note = f'<span class="ctvn-detail ctvn-model">{escape(_model_note(recorded.get(test_id)))}</span>'
        elif run is None or run.problem:
            result, cls = "Sin correr todavía" if run is None else tx.RESULTADO_PRUEBA["sin_correr"], ""
        else:
            r = run.results.get(test_id)
            if r is None:
                result, cls = tx.RESULTADO_PRUEBA["sin_correr"], "fail"
            else:
                result = f"{tx.RESULTADO_PRUEBA[r.status]} · {r.passed} de {r.total} · {tx.segundos(r.seconds)}"
                cls = "" if r.status == "pasa" else "fail"
        rows.append(f'<div class="ctvn-test"><b>{escape(test_id)} · {escape(name)}</b>'
                    f'<em class="{cls}">{escape(result)}</em><span class="ctvn-detail">{escape(checks)}</span>{note}</div>')
    return "".join(rows)


def _run_message(run: pv.LiveRun) -> tuple[str, str]:
    """(kind, text) in newsroom words: success, warning or error."""
    if run.problem == "timeout":
        return "error", (f"Las pruebas tardaron más de {pv.TIMEOUT_S} segundos y se detuvieron. "
                         "Inténtalo de nuevo en un momento.")
    if run.problem:
        return "error", "No se pudieron correr las pruebas en este servidor. Inténtalo de nuevo en un momento."
    passed = sum(1 for r in run.results.values() if r.status == "pasa")
    if run.ok:
        return "success", f"Las {passed} pruebas del reto que corren aquí pasan."
    return "warning", f"Pasan {passed} de {len(pv.LIVE_TESTS)} pruebas del reto. Revisa las marcadas abajo."


def render_jury() -> None:
    """Modo jurado: run the fast challenge tests on the server, on demand, and show each result."""
    st.markdown(section_html("Modo jurado · pruebas del reto en vivo"), unsafe_allow_html=True)
    st.markdown(note_html(f"Corre aquí mismo, en el servidor, las {len(pv.LIVE_TESTS)} pruebas del reto que no "
                          "necesitan el modelo de embeddings. Tarda alrededor de medio minuto."), unsafe_allow_html=True)
    if st.button("Comprobar el reto en vivo", type="primary", key="jury_run"):
        with st.status(f"Corriendo {len(pv.LIVE_TESTS)} pruebas del reto en el servidor…", expanded=True) as status:
            st.write("Esto tarda alrededor de medio minuto. Puedes seguir mirando la página.")
            run = pv.run_live()
            kind, _ = _run_message(run)
            status.update(label=("Pruebas terminadas" if kind != "error" else "Las pruebas no terminaron")
                          + f" · {tx.segundos(run.seconds)}", state="error" if kind == "error" else "complete",
                          expanded=False)
        st.session_state.jury_last = {"run": run, "at": pd.Timestamp.now(tz="UTC")}
    last = st.session_state.get("jury_last")
    run = last["run"] if last else None
    if run is not None:
        kind, text = _run_message(run)
        if kind != "success":  # on success the tiles below already say it
            getattr(st, kind)(text)
        if not run.problem:
            total = sum(r.total for r in run.results.values())
            passed = sum(1 for r in run.results.values() if r.status == "pasa")
            st.markdown(tiles_html([
                ("Pruebas del reto", f"{passed} de {len(pv.LIVE_TESTS)}", f"{total} comprobaciones"),
                ("Tiempo", tx.segundos(run.seconds), "en este servidor"),
                ("Corrida", tx.fecha(last["at"], con_hora=False), f"{tx.fecha(last['at']).split(', ')[-1]}, hora de Panamá"),
            ]), unsafe_allow_html=True)
    st.markdown(_test_rows(run), unsafe_allow_html=True)
