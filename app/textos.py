"""Product words for everything the editor sees (J-15). Owner: Cristian; built with José.

Internal values (contract states, field names, test codes, file paths, guard messages) never reach
the screen as they are: they go through these maps, in plain Spanish for a newsroom. The contract
values themselves do not change; only how they are shown. Pure functions, no Streamlit.
"""

import re

import pandas as pd

PANAMA_TZ = "America/Panama"  # UTC-5, no daylight saving

EVIDENCIA = {"suficiente para el borrador": "Evidencia suficiente", "parcial": "Evidencia parcial",
             "insuficiente": "Evidencia insuficiente"}
PRIORIDAD = {"alto": "prioridad alta", "medio": "prioridad media", "bajo": "prioridad baja"}
TEMA = {"economía": "Economía", "logística/Canal": "Logística y Canal", "turismo": "Turismo",
        "servicios públicos": "Servicios públicos", "eventos naturales": "Eventos naturales",
        "regulación": "Regulación", "otro": "Otros temas"}
CAMPO = {"titulo": "titular", "descripcion": "resumen", "valor": "valor", "place": "lugar",
         "magnitude": "magnitud", "time": "fecha"}
ALCANCE = {"titular/metadatos": "Solo el titular", "descripcion_rss": "Titular y resumen (RSS de TVN)",
           "descripcion_web": "Titular y resumen (web de TVN)"}
ORIGEN_NOTICIA = {"tvn_rss": "TVN (RSS)", "tvn_web": "TVN (web)", "gdelt": "GDELT"}
TIPO_AFIRMACION = {"hecho": "Hecho · lo respalda la fuente citada",
                   "declaracion": "Lo dice una fuente · se atribuye, no se afirma",
                   "inferencia": "Inferencia · se deduce de las fuentes, no se reportó así",
                   "hipotesis": "Hipótesis · falta verificarla"}
REVISION = {"nuevo": "Nuevo", "en revisión": "En revisión", "requiere evidencia": "Requiere evidencia",
            "aprobado como borrador": "Aprobado como borrador", "descartado": "Descartado"}
FORMATO = {"brief": "Resumen", "guion": "Guion de TV", "copy": "Texto para redes"}
COMPONENTE = {"R": "Relación con Panamá", "I": "Impacto", "U": "Urgencia", "N": "Novedad", "E": "Evidencia"}
ORIGEN_RESPUESTA = {"cache": "respuesta guardada", "llm": "respuesta nueva", "sin_evidencia": "sin información",
                    "offline_miss": "sin conexión", "error": "no se pudo responder"}

# Abstention reasons written by the code (not by the model), in product words.
MOTIVO = {
    "No hay evidencia en el corpus para esta consulta; no se responde con datos no verificados.":
        "No encontré noticias ni datos oficiales sobre esto, así que no respondo para no inventar.",
    "Sin internet y sin respuesta guardada en caché para esta consulta.":
        "Sin conexión solo puedo mostrar respuestas guardadas, y esta pregunta no está entre ellas.",
    "El proveedor del LLM no respondió; no se generó borrador.":
        "El servicio de IA no respondió. Intenta de nuevo en un momento.",
    "La salida fue bloqueada por seguridad.":
        "Bloqueé la respuesta por seguridad: podía revelar la configuración del sistema.",
}


def tema(value) -> str:
    return "Sin tema" if value is None or pd.isna(value) else TEMA.get(value, str(value).capitalize())


def evidencia(value) -> str:
    return EVIDENCIA.get(value, "Evidencia sin dato")


def limpiar_titular(value) -> str:
    """Headline as a person writes it: GDELT tokenizes titles ('¿ Cómo está … ?'); only spacing changes."""
    if value is None or pd.isna(value):
        return "Sin titular"
    text = re.sub(r"\s+([?!.,;:%)»”])", r"\1", str(value))
    text = re.sub(r"([¿¡(«“])\s+", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def fecha(ts, con_hora: bool = True) -> str:
    """Panama local time as dd/MM/yyyy and a 12-hour clock ('30/09/2026, 2:00 p. m.'); null says so."""
    if ts is None or (not isinstance(ts, str) and pd.isna(ts)):
        return "sin fecha"
    t = pd.Timestamp(ts)
    t = (t.tz_localize("UTC") if t.tzinfo is None else t).tz_convert(PANAMA_TZ)
    if not con_hora:
        return t.strftime("%d/%m/%Y")
    hour = t.hour % 12 or 12
    return f"{t.strftime('%d/%m/%Y')}, {hour}:{t.minute:02d} {'a. m.' if t.hour < 12 else 'p. m.'}"


def notas_y_fuentes(n_registros, n_procedencias) -> str:
    """'7 notas de 7 fuentes independientes'; replicas of one agency count as one source (ADR-007)."""
    if n_registros is None or pd.isna(n_registros):
        return "Sin dato de notas"
    notas, fuentes = int(n_registros), None if pd.isna(n_procedencias) else int(n_procedencias)
    notas_txt = f"{notas} nota" + ("" if notas == 1 else "s")
    if fuentes is None:
        return notas_txt
    if notas > 1 and fuentes == 1:
        return f"{notas_txt}, todas de la misma fuente original"
    return f"{notas_txt} de {fuentes} fuente" + (" independiente" if fuentes == 1 else "s independientes")


def palabras(n: int, high: int) -> str:
    return f"{n} palabras · hasta {high}"


def alerta(texto: str) -> str:
    """Security alerts (T07) in product words; the raw text stays in the guard report."""
    t = (texto or "").lower()
    if "en la consulta" in t:
        return ("Tu pregunta incluye una orden para el sistema (por ejemplo, «ignora tus instrucciones»). "
                "No la seguí: solo respondo con lo que dicen las fuentes.")
    if "salida bloqueada" in t:
        return "Bloqueé la respuesta porque podía revelar la configuración del sistema."
    return ("Una de las fuentes trae instrucciones escritas para el sistema. La traté como dato y no la obedecí; "
            "no la uses como hecho.")


def retiro(violacion: str) -> str | None:
    """Why the guard removed the running text, in product words; None for what the editor need not see."""
    v = (violacion or "").lower()
    if "cifras sin respaldo" in v:
        return "Quité el texto corrido porque tenía cifras que no aparecen en las fuentes."
    if "repite una instrucción" in v:
        return "Quité el texto corrido porque repetía una orden escrita en una fuente."
    if "borrador descartado" in v:
        return "Quité el texto corrido porque tenía frases sin fuente."
    if "palabras, fuera de" in v:
        return "El texto quedó fuera del largo permitido, así que no lo muestro."
    return None


def motivo(texto: str | None) -> str:
    return MOTIVO.get(texto or "", texto or "La evidencia no alcanza para responder.")


def cita_fuente(campo: str | None) -> str:
    return CAMPO.get(campo or "", campo or "campo sin nombre")
