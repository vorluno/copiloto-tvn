"""Topic classification (B-07). Owner: B.

Each topic is described by a few Spanish sentences. A news item's score for a topic is
its best cosine similarity to that topic's sentences; tema is the best topic and
tema_confianza that similarity. Below THRESHOLD the item is "otro": a weak match is not
forced into a topic. THRESHOLD was calibrated by B-12 (outputs/reports/clasificacion.md) on half of the
human labels and reported on the other half.

Sports, crime, entertainment and foreign news with no Panama link have no description
on purpose: they should land under the threshold and become "otro".
"""

import numpy as np
import pandas as pd

from src.nlp.embed import MODEL_NAME, encode

TOPICS = ["economía", "logística/Canal", "turismo", "servicios públicos", "eventos naturales", "regulación"]
OTHER = "otro"
THRESHOLD = 0.45  # B-12 (7 oct): best macro-F1 on the calibration half of the human labels (was 0.50 from a 20-headline check)

DESCRIPTIONS = {
    "economía": [
        "Noticia sobre la economía de Panamá: crecimiento, inflación, precios, empleo y salarios.",
        "Comercio, inversión, bancos, créditos, deuda pública, presupuesto del Estado e impuestos.",
        "Precios de alimentos y de la canasta básica, costo de vida y consumo de los hogares.",
    ],
    "logística/Canal": [
        "Canal de Panamá: tránsitos de buques, esclusas, peajes, calado y agua del lago Gatún.",
        "Puertos, navieras, contenedores, carga marítima, transporte y cadena logística.",
        "Comercio marítimo internacional, rutas de carga y la Autoridad del Canal de Panamá.",
    ],
    "turismo": [
        "Turismo en Panamá: llegada de visitantes, hoteles, cruceros, vuelos y aerolíneas.",
        "Destinos turísticos, playas, temporada alta, ocupación hotelera y promoción turística.",
    ],
    "servicios públicos": [
        "Servicios públicos: agua potable, Idaan, electricidad, cortes de luz y recolección de basura.",
        "Transporte público, metro, buses, carreteras y obras de infraestructura del Estado.",
        "Salud pública, hospitales, Caja de Seguro Social, educación pública y escuelas.",
    ],
    "eventos naturales": [
        "Eventos naturales: sismos, terremotos, lluvias intensas, inundaciones y deslizamientos.",
        "Sequía, fenómeno de El Niño, tormentas, huracanes, alertas del clima y Sinaproc.",
    ],
    "regulación": [
        "Regulación: leyes, decretos, reformas aprobadas por la Asamblea Nacional y normas del gobierno.",
        "Resoluciones de entes reguladores, superintendencias, permisos, sanciones y fallos de la Corte.",
    ],
}


def topic_matrix(name: str = MODEL_NAME) -> tuple[np.ndarray, list[str]]:
    """(sentence vectors, topic of each row)."""
    labels = [topic for topic in TOPICS for _ in DESCRIPTIONS[topic]]
    sentences = [s for topic in TOPICS for s in DESCRIPTIONS[topic]]
    return encode(sentences, name), labels


def topic_scores(vectors: np.ndarray, name: str = MODEL_NAME) -> pd.DataFrame:
    """One column per topic: the best similarity to any of its sentences."""
    sentence_vectors, labels = topic_matrix(name)
    sims = vectors @ sentence_vectors.T
    frame = pd.DataFrame(sims, columns=labels)
    return frame.T.groupby(level=0).max().T[TOPICS]


def classify(vectors: np.ndarray, threshold: float = THRESHOLD, name: str = MODEL_NAME) -> pd.DataFrame:
    """tema and tema_confianza for each row of `vectors`, same order."""
    scores = topic_scores(vectors, name)
    best = scores.idxmax(axis=1)
    confidence = scores.max(axis=1).astype("float64")
    topic = best.where(confidence >= threshold, OTHER)
    return pd.DataFrame({"tema": topic.astype(object), "tema_confianza": confidence.round(4)})
