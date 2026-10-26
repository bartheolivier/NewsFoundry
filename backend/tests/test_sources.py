from agent import ChatDeps, SOURCES_HEADER, _record_source, ensure_sources_section


SOURCES = [
    {"url": "https://ex.com/a", "title": "Wall Street en hausse", "source": "L'Echo", "date": "2026-10-06"},
    {"url": "https://ex.com/b", "title": "Tesla [record]", "source": "", "date": ""},
]


def test_sources_appended_when_model_omits_them():
    out = ensure_sources_section("Synthèse sans aucun lien.", SOURCES)
    assert SOURCES_HEADER in out
    assert "[Wall Street en hausse](https://ex.com/a) — L'Echo (2026-10-06)" in out
    # Brackets in titles must not break Markdown links
    assert "[Tesla (record)](https://ex.com/b)" in out


def test_existing_sources_section_is_kept_untouched():
    text = "Texte [Wall Street en hausse](https://ex.com/a)\n\n### 📰 Sources consultées\n- [x](https://ex.com/a)"
    assert ensure_sources_section(text, SOURCES) == text


def test_no_sources_means_no_section():
    assert ensure_sources_section("Réponse générale.", []) == "Réponse générale."


def test_record_source_deduplicates_and_tracks_urls():
    deps = ChatDeps()
    _record_source(deps, "https://ex.com/a", title="A")
    _record_source(deps, "https://ex.com/a", title="A bis")
    assert deps.loaded_articles == ["https://ex.com/a"]
    assert len(deps.turn_sources) == 1


def test_record_source_deduplicates_by_tracking_params_and_title():
    deps = ChatDeps()
    _record_source(deps, "https://ex.com/article-1?utm_source=twitter", title="Mobilisation lycéens à Matignon")
    # Même URL de base sans tracking
    _record_source(deps, "https://ex.com/article-1", title="Mobilisation lycéens à Matignon")
    # Même titre ou quasi-identique sur un autre domaine (syndication AFP)
    _record_source(deps, "https://autre-journal.fr/depeche", title="Mobilisation lycéens à Matignon")
    assert len(deps.turn_sources) == 1


def test_ensure_sources_section_deduplicates_repeated_bullets():
    input_text = """Synthèse sur la crise.

### 📰 Sources consultées
- [Crise sociale. Reçus à Matignon](https://ex.com/1) — AFP (2026-10-26)
- [Colère lycéenne : débat sur Parcoursup](https://ex.com/2) — Rédaction (2026-10-26)
- [Colère lycéenne : débat sur Parcoursup](https://ex.com/2) — Rédaction (2026-10-26)
- [Maintien de l'ordre : Macron](https://ex.com/3) — Rédaction (2026-10-26)
- [Crise sociale. Reçus à Matignon](https://ex.com/1) — AFP (2026-10-26)
"""
    cleaned = ensure_sources_section(input_text, [])
    assert cleaned.count("Matignon") == 1
    assert cleaned.count("Parcoursup") == 1
    assert cleaned.count("Macron") == 1
    assert cleaned.count("https://ex.com/1") == 1
    assert cleaned.count("https://ex.com/2") == 1

