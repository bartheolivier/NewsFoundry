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
