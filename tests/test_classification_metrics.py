"""B-12 metrics: macro-F1 by topic and pairwise precision/recall. Owner: B.

Hand-made labels; exact numbers.
"""

import pandas as pd

from src.eval.classification import LABELS, blind_events, calibrate, load_labels, predict, split_halves
from src.eval.metrics import pairwise, topic_f1


def test_topic_f1_counts_and_skips_unmeasured_topics():
    m = topic_f1(["economía", "otro", "economía"], ["economía", "economía", "otro"], LABELS)
    eco, oth = m["per_topic"]["economía"], m["per_topic"]["otro"]
    assert (eco["tp"], eco["fp"], eco["fn"]) == (1, 1, 1) and eco["f1"] == 0.5
    assert (oth["tp"], oth["fp"], oth["fn"]) == (0, 1, 1) and oth["f1"] == 0.0
    assert m["per_topic"]["turismo"]["f1"] is None  # no true or predicted item: not measured, not 0
    assert m["n_temas"] == 2 and m["macro_f1"] == 0.25


def test_pairwise_precision_and_recall_with_numerators():
    ids = ["a", "b", "c", "d"]
    truth = [1, 1, 2, 3]       # a-b same event
    predicted = [7, 7, 7, 8]   # a-b-c grouped
    precision, recall = pairwise(truth, predicted, ids)
    assert (precision.numerator, precision.denominator) == (1, 3)  # a-b ok; a-c, b-c wrong
    assert (recall.numerator, recall.denominator) == (1, 1)
    assert precision.failures == ["a · c", "b · c"]


def test_labels_are_validated_and_empty_rows_reported(tmp_path):
    path = tmp_path / "etiquetas.csv"
    pd.DataFrame([
        {"id_noticia": "N-1", "tema_humano": "Economía", "cluster_humano": "1", "etiquetador": "C", "nota": ""},
        {"id_noticia": "N-2", "tema_humano": "", "cluster_humano": "", "etiquetador": "", "nota": ""},
        {"id_noticia": "N-3", "tema_humano": "deportes", "cluster_humano": "2", "etiquetador": "C", "nota": ""},
    ]).to_csv(path, index=False)
    labeled, problems = load_labels(path)
    assert labeled["tema_humano"].tolist() == ["economía"]  # case-insensitive, written as in the contract
    assert len(problems) == 2


def test_halves_are_fixed_and_balanced():
    ids = pd.Series([f"N-{i:010x}" for i in range(60)])
    first = split_halves(ids)
    assert first.sum() == 30
    assert split_halves(ids[::-1]).sort_index().tolist() == first.tolist()  # order does not matter


def test_threshold_calibration_picks_the_best_macro_f1():
    scores = pd.DataFrame({t: [0.0] * 4 for t in LABELS}, index=["a", "b", "c", "d"])
    scores.loc["a", "economía"] = 0.62
    scores.loc["b", "economía"] = 0.58
    scores.loc["c", "turismo"] = 0.41
    scores.loc["d", "turismo"] = 0.36
    truth = pd.Series(["economía", "economía", "otro", "otro"], index=scores.index)
    threshold, table = calibrate(scores, truth)
    assert predict(scores, threshold).tolist() == truth.tolist()
    assert 0.45 <= threshold <= 0.55


def test_labels_corrected_after_seeing_the_system_go_back_to_their_own_event():
    labeled = pd.DataFrame({"cluster_humano": ["9", "9", "3", "3"],
                            "nota": ["corregido después de comparar con el sistema", "Corregido tras comparar con el sistema",
                                     "", "duda"]}, index=["a", "b", "c", "d"])
    blind = blind_events(labeled)
    assert blind["a"] != blind["b"]  # both corrected: separate again, as in the blind delivery
    assert blind["c"] == blind["d"] == "3"
