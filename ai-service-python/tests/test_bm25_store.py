"""Tests for the multilingual BM25 tokenizer and version-aware index loader."""

import pickle
from pathlib import Path


from app.rag.bm25_store import BM25_INDEX_VERSION, BM25Store, _tokenize_text


class TestFrenchTokenization:
    def test_case_and_punctuation_collapse_to_same_stem(self):
        variants = ["Procédure", "procédures", "PROCÉDURE", "procédure,", "procédure."]
        stems = {tuple(_tokenize_text(v)) for v in variants}
        assert len(stems) == 1, f"Expected one stem across {variants}, got {stems}"

    def test_domain_stopwords_dropped(self):
        # `selon`, `conformément`, `article`, `document`, `du`, `à`, `la`, `l`
        # should all be filtered. Only meaningful stems should remain.
        toks = _tokenize_text("Selon la procédure, conformément à l'article 4.2.1 du document")
        # The numeric run "4.2.1" gets caught by the token regex via "421"-ish
        # behavior; we only assert that none of the explicit stopwords leaked through.
        for stop in ("selon", "la", "à", "l", "du", "article", "document", "conformement"):
            assert stop not in toks

    def test_negations_preserved(self):
        # `non` and `pas` carry meaning in regulatory text — must NOT be stripped.
        toks = _tokenize_text("non conforme")
        assert "non" in toks

    def test_diacritics_folded(self):
        # café and cafe should produce identical tokens after folding+stem
        assert _tokenize_text("café") == _tokenize_text("cafe")

    def test_empty_and_whitespace(self):
        assert _tokenize_text("") == []
        assert _tokenize_text("   \n\t  ") == []

    def test_short_tokens_dropped(self):
        # Single-letter noise tokens (a, l, d as standalone) are dropped via len<2
        toks = _tokenize_text("a b c")
        assert toks == []


class TestArabicTokenization:
    def test_tashkeel_stripped(self):
        with_tashkeel = _tokenize_text("الجَوْدَة")
        without = _tokenize_text("الجودة")
        assert with_tashkeel == without
        assert with_tashkeel == ["الجودة"]

    def test_arabic_not_accent_folded(self):
        # Arabic letters must survive — accent-folding would mangle them to ASCII.
        toks = _tokenize_text("الإنتاج")
        assert toks
        # Must still contain Arabic characters
        assert any("؀" <= c <= "ۿ" for c in toks[0])

    def test_arabic_function_words_dropped(self):
        toks = _tokenize_text("في المختبر على الجودة")
        assert "في" not in toks
        assert "على" not in toks


class TestMixedScripts:
    def test_french_arabic_mixed(self):
        toks = _tokenize_text("La procédure الجودة est conforme")
        # French tokens stemmed, Arabic preserved with letters intact
        assert any(t.startswith("procedur") for t in toks)
        assert any("؀" <= c <= "ۿ" for t in toks for c in t)


class TestBM25IndexVersioning:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        store = BM25Store()
        store.build_index(
            texts=["la procédure qualité", "le contrôle des médicaments"],
            vector_store_ids=["id1", "id2"],
        )
        path = str(tmp_path / "bm25.pkl")
        store.save(path)

        store2 = BM25Store()
        store2.load(path)
        assert store2.size == 2
        assert store2.bm25 is not None

    def test_load_discards_old_version(self, tmp_path: Path):
        path = tmp_path / "bm25.pkl"
        legacy_payload = {
            # No "version" key — represents v0/legacy pickles from before the bump.
            "corpus_texts": [["procedure"], ["controle"]],
            "corpus_ids": ["id1", "id2"],
        }
        path.write_bytes(pickle.dumps(legacy_payload))

        store = BM25Store()
        store.load(str(path))
        # Should refuse to load mismatched-version index
        assert store.size == 0
        assert store.bm25 is None

    def test_load_discards_explicit_old_version(self, tmp_path: Path):
        path = tmp_path / "bm25.pkl"
        older = {
            "version": BM25_INDEX_VERSION - 1,
            "corpus_texts": [["x"]],
            "corpus_ids": ["id1"],
        }
        path.write_bytes(pickle.dumps(older))

        store = BM25Store()
        store.load(str(path))
        assert store.size == 0


class TestBM25SearchQuality:
    """End-to-end smoke checks that the tokenization improvements actually surface
    documents that the old `text.lower().split()` would miss."""

    def test_query_matches_inflected_form(self):
        store = BM25Store()
        store.build_index(
            texts=[
                "Les procédures qualité sont obligatoires en production pharmaceutique.",
                "Le contrôle des matières premières suit la norme ISO.",
                "Les résultats des tests sont enregistrés dans le système GMP.",
            ],
            vector_store_ids=["proc", "ctrl", "test"],
        )
        # Query uses singular "procédure" — should find doc containing plural "procédures"
        results = store.search("procédure pharmaceutique", top_k=3)
        assert results, "Expected at least one match"
        assert results[0][0] == "proc"

    def test_query_matches_uppercase_accent_variants(self):
        # Need >2 docs because BM25Okapi IDF goes to zero on tiny corpora when
        # the term appears in exactly half of the corpus.
        store = BM25Store()
        store.build_index(
            texts=[
                "La QUALITÉ pharmaceutique est essentielle.",
                "Le contrôle des matières premières est strict.",
                "Les tests microbiologiques sont effectués chaque jour.",
                "Les déviations sont enregistrées dans le système.",
            ],
            vector_store_ids=["q", "c", "t", "d"],
        )
        # ASCII query "qualite" should match accented "QUALITÉ"
        results = store.search("qualite", top_k=4)
        assert results, "Expected accent-folded match"
        assert results[0][0] == "q"

    def test_empty_query_returns_empty(self):
        store = BM25Store()
        store.build_index(texts=["test"], vector_store_ids=["t"])
        # Query that tokenizes to nothing (only stopwords/punctuation)
        assert store.search("la le des", top_k=5) == []
