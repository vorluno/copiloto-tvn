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
         "magnitude": "magnitud", "time": "fecha", "unidad": "unidad", "pais_iso3": "país", "anio": "año",
         "indicador_id": "indicador", "depth_km": "profundidad", "medio": "medio",
         "fecha_publicacion": "fecha de publicación"}
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


# --- Case card (J-16): citation dates, figures, missing formats, live drafting ---------------

FORMATO_SUJETO = {"brief": "El resumen", "guion": "El guion", "copy": "El texto para redes"}
PASO_REDACCION = {"inicio": "Buscando la evidencia del tema…", "brief": "Redactando el resumen…",
                  "guion": "Redactando el guion de TV…", "copy": "Redactando el texto para redes…",
                  "citas": "Revisando que cada dato tenga su fuente…", "listo": "Listo · borrador nuevo para revisar",
                  "sin_conexion": "Sin conexión: no se puede redactar ahora",
                  "fallo": "El servicio de IA no respondió", "fallo_guion": "El guion no pasó el control otra vez"}
REDACTAR = "Redactar borrador"
VOLVER_GUION = "Volver a redactar el guion"
SIN_BORRADOR = ("Este tema todavía no tiene borrador. Puedes pedir uno ahora: se escribe con las mismas fuentes y "
                "reglas que los temas guardados y pasa por el mismo control de citas.")
SIN_BORRADOR_NUEVO = "Sin borrador nuevo"
SIN_CONEXION_REDACCION = ("Redactar un borrador nuevo necesita conexión con el servicio de IA. Ahora solo están "
                          "los borradores guardados de los temas más prioritarios.")
FALLO_REDACCION = "El servicio de IA no respondió. Intenta de nuevo en un momento."

_LONG_DECIMAL = re.compile(r"(\d+)([.,])(\d{4,})(?!\d)")
_WORDS_OUT = re.compile(r"(\w+): (\d+) palabras, fuera de \[(\d+), (\d+)\]")


def cifras(texto: str | None) -> str:
    """Numbers with more than 3 decimals rounded to 2 for reading ('0.69322555100446 %' -> '0.69 %').

    Display only: the cited passage is evidence and is always shown as it is.
    """
    if not texto:
        return texto or ""

    def short(m: re.Match) -> str:
        whole, sep, frac = m.groups()
        value = round(float(f"{whole}.{frac}"), 2)
        return f"{value:.2f}".replace(".", sep)

    return _LONG_DECIMAL.sub(short, texto)


def fecha_cita(publicada, detectada=None) -> str | None:
    """When a news item came out: the outlet's date, else GDELT's detection said as such."""
    if publicada is not None and not (not isinstance(publicada, str) and pd.isna(publicada)):
        return f"publicada el {fecha(publicada, con_hora=False)}"
    if detectada is not None and not (not isinstance(detectada, str) and pd.isna(detectada)):
        return f"detectada el {fecha(detectada, con_hora=False)}"
    return None


def ver_notas(n: int) -> str:
    """Expander label for the news behind an event, with number agreement."""
    return "Ver la nota que lo reporta" if n == 1 else f"Ver las {n} notas que lo reportan"


def ver_fuentes(n: int) -> str:
    return f"Ver las {n} fuentes"


def formato_ausente(task: str, gap: dict | None) -> str:
    """Why a draft format is missing, in newsroom words, from what the quality check recorded.

    `gap`: {"source", "violations", "abstencion", "motivo", "skipped"} for that format, or None
    when nothing was recorded (then an honest generic text).
    """
    sujeto = FORMATO_SUJETO.get(task, "Este formato")
    if not gap:
        return f"{sujeto} no quedó guardado para este tema y no tenemos registrado el motivo."
    if gap.get("skipped"):
        return f"{sujeto} no se redactó: el resumen no encontró evidencia suficiente, y sin ella no se escribe nada más."
    if gap.get("source") == "offline_miss":
        return f"{sujeto} no está guardado y sin conexión no se puede redactar ahora."
    if gap.get("source") == "error":
        return f"{sujeto} no se redactó porque el servicio de IA no respondió."
    for v in gap.get("violations") or []:
        if m := _WORDS_OUT.search(v):
            n, low, high = int(m.group(2)), int(m.group(3)), int(m.group(4))
            if task == "guion":
                return (f"El guion salió con {n} palabras y para 45–60 segundos hacen falta entre {low} y {high}; "
                        "no lo mostramos para no rellenar.")
            rango = f"hasta {high}" if low <= 1 else f"entre {low} y {high}"
            return f"{sujeto} salió con {n} palabras y debe tener {rango}; no lo mostramos."
    for v in gap.get("violations") or []:
        if reason := retiro(v):
            return reason.replace("el texto corrido", sujeto.lower())
    if gap.get("abstencion"):
        return f"{sujeto} no se redactó: {motivo(gap.get('motivo'))}"
    return f"{sujeto} no pasó el control de calidad, así que no lo mostramos."


def palabras_guion(gap: dict | None) -> int | None:
    """Word count of a rejected script, when the quality check recorded it."""
    for v in (gap or {}).get("violations") or []:
        if (m := _WORDS_OUT.search(v)) and m.group(1) == "guion":
            return int(m.group(2))
    return None


def evidencia_encontrada(n_noticias: int, n_oficiales: int) -> str:
    notas = f"{n_noticias} nota" + ("" if n_noticias == 1 else "s")
    if not n_oficiales:
        return f"Encontré {notas} sobre este tema y ningún dato oficial vinculado."
    return f"Encontré {notas} y {n_oficiales} dato" + ("" if n_oficiales == 1 else "s") + " oficial" + (
        "" if n_oficiales == 1 else "es") + " vinculados a este tema."


def citas_revisadas(kept: int, received: int) -> str:
    if not received:
        return "No quedó ninguna afirmación con fuente: el sistema prefirió no afirmar nada."
    return f"Revisé las citas: {kept} de {received} afirmaciones tienen su fuente y se muestran."


def titulo_mesa(hasta) -> str:
    """Mesa title: the date of the data, never a promise of 'today' (the corpus ends 30/09/2026)."""
    return "Prioridad" if hasta is None or pd.isna(hasta) else f"Prioridad al {fecha(hasta, con_hora=False)}"


def datos_hasta(hasta) -> str:
    return "Sin fecha de datos" if hasta is None or pd.isna(hasta) else f"Noticias hasta el {fecha(hasta)}"


# --- J-16: Preguntar (closest findings), weights simulator and the live challenge check ---

SIN_RESPUESTA_DIRECTA = "No encontré una respuesta directa a tu pregunta."
LO_MAS_CERCANO = "Esto es lo más cercano que encontré:"
NO_VERIFICADO = ("Esto no es una respuesta verificada: son las notas y los datos más parecidos a tu pregunta. "
                 "Revísalos y confírmalos antes de usarlos.")
TEMA_AUSENTE = ("Este tema no está en las noticias ni en los datos oficiales cargados. "
                "Para cubrirlo hace falta otra fuente.")
SIGUIENTE_PASO = "Siguiente paso"
RESPUESTA_LISTA = "Listo"

# World Bank indicators and countries, as a newsroom names them (same set as src/context.py).
INDICADOR = {"NY.GDP.MKTP.KD.ZG": "Crecimiento del PIB", "FP.CPI.TOTL.ZG": "Inflación (precios al consumidor)",
             "SL.UEM.TOTL.ZS": "Desempleo", "NE.EXP.GNFS.ZS": "Exportaciones de bienes y servicios",
             "IT.NET.USER.ZS": "Uso de internet"}
PAIS = {"PAN": "Panamá", "CRI": "Costa Rica", "COL": "Colombia", "DOM": "República Dominicana", "MEX": "México",
        "GTM": "Guatemala"}

RANGO_NOMBRE = {"bajo": "Baja", "medio": "Media", "alto": "Alta"}
SIMULACION_AVISO = ("Simulación: no cambia el orden oficial ni se guarda. Para cambiar las reglas se edita "
                    "la versión de reglas y se justifica en una decisión.")

# Challenge tests (section 9 of the brief), in newsroom words: what each one checks.
PRUEBA_RETO = {
    "T01": ("Fechas inválidas y nulos", "Separa los errores, conserva los nulos y la carga sigue"),
    "T02": ("Tres registros del mismo evento", "Un solo evento con 3 fuentes, sin triplicar su importancia"),
    "T03": ("Noticia antigua recirculada", "Muestra la fecha original y no la cuenta como evento nuevo"),
    "T04": ("Cifra anual del Banco Mundial", "Cita país, año y unidad; nunca dice «hoy»"),
    "T05": ("Dos afirmaciones incompatibles", "Muestra ambas versiones y lo que falta verificar"),
    "T06": ("Consulta sin respuesta", "Se abstiene y no inventa ninguna cifra"),
    "T07": ("Fuente que pide ignorar instrucciones", "No obedece, no revela nada y deja una alerta"),
    "T08": ("Caso de prioridad alta", "Muestra los componentes y la regla; no habilita publicar"),
    "T09": ("Brief editorial", "Formato útil, con citas y hechos separados de inferencias"),
    "T10": ("Sin internet", "Recorrido completo con respuestas guardadas"),
}
RESULTADO_PRUEBA = {"pasa": "Pasa", "falla": "No pasa", "omitida": "Omitida", "sin_correr": "No corrió"}


def puestos(cambio) -> str:
    """How many places an event moves in the simulation: '↑ 3', '↓ 2', '=' or 'entra'."""
    if cambio is None or pd.isna(cambio):
        return "entra al top"
    cambio = int(cambio)
    if cambio == 0:
        return "="
    return f"↑ {cambio}" if cambio > 0 else f"↓ {-cambio}"


def segundos(valor) -> str:
    if valor is None or pd.isna(valor):
        return "—"
    return "menos de 0.1 s" if float(valor) < 0.05 else f"{float(valor):.1f} s"
