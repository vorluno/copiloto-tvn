"""Sample of 60 news for the human labels (C-05). Owner: B.

Built on a small synthetic corpus, so no test depends on the real data.
"""

import pandas as pd
import pytest

from src.nlp.label_sample import (
    LABEL_COLUMNS,
    N_NEIGHBORS,
    N_TOTAL,
    OUTPUT_COLUMNS,
    build_sample,
    write_sample,
)


def corpus(n: int = 200) -> pd.DataFrame:
    """Synthetic news: 40 events with 5 near-identical headlines each, spread over a year."""
    rows = []
    for i in range(n):
        event = i // 5
        day = pd.Timestamp("2025-10-05T12:00:00Z") + pd.Timedelta(days=8 * event, hours=i % 5)
        rows.append({
            "id_noticia": f"N-{i:010x}",
            "titulo": f"Evento {event} sobre tema{event} en la ciudad{event} version {i % 5}",
            "descripcion": None,
            "medio": f"medio{i % 7}",
            "idioma": "zh" if i % 23 == 0 else "es",
            "fecha_publicacion": day if i % 2 == 0 else pd.NaT,
            "fecha_deteccion": pd.NaT if i % 2 == 0 else day,
            "origen": "gdelt" if i % 2 else "tvn_web",
        })
    df = pd.DataFrame(rows)
    for col in ("fecha_publicacion", "fecha_deteccion"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def test_sample_has_60_unique_news_in_readable_languages():
    sample, _ = build_sample(corpus(), seed=7)
    assert len(sample) == N_TOTAL == 60
    assert sample["id_noticia"].is_unique
    news = corpus().set_index("id_noticia")
    assert set(news.loc[sample["id_noticia"], "idioma"]) <= {"es", "en"}


def test_same_seed_same_sample_and_order():
    a, _ = build_sample(corpus(), seed=7)
    b, _ = build_sample(corpus(), seed=7)
    pd.testing.assert_frame_equal(a, b)
    c, _ = build_sample(corpus(), seed=8)
    assert list(a["id_noticia"]) != list(c["id_noticia"])


def test_neighbors_are_close_in_time_and_text():
    _, pairs = build_sample(corpus(), seed=7)
    assert len(pairs) == N_NEIGHBORS
    news = corpus().set_index("id_noticia")
    when = news["fecha_publicacion"].fillna(news["fecha_deteccion"])
    for seed_id, neighbor_id, similarity in pairs.itertuples(index=False):
        assert seed_id != neighbor_id
        assert abs(when[seed_id] - when[neighbor_id]) <= pd.Timedelta(hours=72)
        assert similarity > 0


def test_output_columns_and_empty_labels():
    sample, _ = build_sample(corpus(), seed=7)
    assert list(sample.columns) == OUTPUT_COLUMNS
    assert OUTPUT_COLUMNS[:5] == LABEL_COLUMNS == ["id_noticia", "tema_humano", "cluster_humano", "etiquetador", "nota"]
    for col in LABEL_COLUMNS[1:]:
        assert (sample[col] == "").all()


def test_never_overwrites_a_file_with_labels(tmp_path):
    sample, _ = build_sample(corpus(), seed=7)
    path = tmp_path / "etiquetas_humanas.csv"
    write_sample(sample, path)
    labeled = pd.read_csv(path, dtype=str, keep_default_na=False)
    labeled.loc[0, "tema_humano"] = "economía"
    labeled.to_csv(path, index=False)
    with pytest.raises(FileExistsError):
        write_sample(sample, path)


def test_header_only_file_can_be_replaced(tmp_path):
    path = tmp_path / "etiquetas_humanas.csv"
    path.write_text(",".join(LABEL_COLUMNS) + "\n", encoding="utf-8")
    sample, _ = build_sample(corpus(), seed=7)
    write_sample(sample, path)
    assert len(pd.read_csv(path)) == 60
