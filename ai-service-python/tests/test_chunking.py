
from app.services.chunking import RegulatoryChunker, TextChunker


class TestTextChunker:
    def setup_method(self):
        self.chunker = TextChunker(chunk_size=50, chunk_overlap=10)

    def test_empty_text(self):
        chunks = self.chunker.chunk_text("")
        assert chunks == []

    def test_whitespace_only(self):
        chunks = self.chunker.chunk_text("   \n\n   ")
        assert chunks == []

    def test_short_text_single_chunk(self):
        text = "This is a short text."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_chunk_indices_sequential(self):
        # Create text long enough for multiple chunks
        text = "This is a sentence. " * 50
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_size_respected(self):
        text = "This is a test sentence for chunking. " * 100
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text(text)
        for chunk in chunks:
            assert chunk.token_count <= 110  # Allow small margin

    def test_overlap_produces_more_chunks(self):
        text = "Word " * 200
        no_overlap = TextChunker(chunk_size=50, chunk_overlap=0)
        with_overlap = TextChunker(chunk_size=50, chunk_overlap=10)
        chunks_no = no_overlap.chunk_text(text)
        chunks_with = with_overlap.chunk_text(text)
        assert len(chunks_with) >= len(chunks_no)

    def test_paragraph_splitting(self):
        text = "First paragraph content.\n\nSecond paragraph content."
        chunker = TextChunker(chunk_size=500, chunk_overlap=0)
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 1

    def test_token_count_positive(self):
        text = "Every chunk should have a positive token count."
        chunks = self.chunker.chunk_text(text)
        for chunk in chunks:
            assert chunk.token_count > 0

    def test_french_abbreviations_not_split(self):
        # pysbd should keep "Cf. Art. 7" and "n° 12" together — the old
        # `[.!?]\s+` regex would have split on each period.
        text = "Voir Cf. Art. 7 du règlement n° 12 pour le détail."
        chunks = TextChunker(chunk_size=200, chunk_overlap=0).chunk_text(text)
        # Whole input is one sentence — must fit in a single chunk.
        assert len(chunks) == 1
        assert "Cf. Art. 7" in chunks[0].content


class TestRegulatoryChunker:
    SOP = """CHAPITRE 1 — Objet et domaine
Cette procédure décrit le contrôle qualité.
Elle s'applique à tous les sites de Sothema.

Article 4 — Échantillonnage
Les échantillons sont prélevés selon §4.2.

4.2 Méthodes de prélèvement
4.2.1 Prélèvement aseptique
Effectuer sous flux laminaire de classe A. Cf. Art. 7 du Pharmacopée Européenne.

4.2.2 Prélèvement non aseptique
Pour les matières inertes, prélèvement en zone D. Résultats sous nº 12.
"""

    def test_emits_chunks(self):
        chunks = RegulatoryChunker(chunk_size=200, document_title="SOP-001").chunk_text(self.SOP)
        assert chunks
        assert all(c.token_count > 0 for c in chunks)
        assert all(c.chunk_index == i for i, c in enumerate(chunks))

    def test_breadcrumbs_include_document_and_section_path(self):
        chunks = RegulatoryChunker(chunk_size=200, document_title="SOP-001").chunk_text(self.SOP)
        # Every chunk should carry a breadcrumb starting with the doc title.
        for c in chunks:
            assert c.breadcrumb.startswith("SOP-001")

        # The deepest chunk (4.2.1 content) must carry the full ancestor path.
        deep = next(c for c in chunks if "Effectuer sous flux laminaire" in c.content)
        assert "Chapitre 1" in deep.breadcrumb
        assert "Article 4" in deep.breadcrumb
        assert "4.2 Méthodes" in deep.breadcrumb
        assert "4.2.1" in deep.breadcrumb

    def test_breadcrumb_does_not_double_separator(self):
        # Em-dash separator in source headings must not produce "Article 4 — — Title"
        chunks = RegulatoryChunker(chunk_size=200, document_title="SOP-001").chunk_text(self.SOP)
        for c in chunks:
            assert " — — " not in c.breadcrumb, c.breadcrumb

    def test_for_indexing_prepends_breadcrumb(self):
        chunks = RegulatoryChunker(chunk_size=200, document_title="SOP-001").chunk_text(self.SOP)
        deep = next(c for c in chunks if "Effectuer sous flux laminaire" in c.content)
        indexed = deep.for_indexing()
        # Breadcrumb leads, content follows
        assert indexed.startswith(deep.breadcrumb)
        assert deep.content in indexed

    def test_breadcrumbs_pop_on_new_chapter(self):
        text = """CHAPITRE 1 — Premier
Texte du premier chapitre.

CHAPITRE 2 — Second
Texte du second chapitre.
"""
        chunks = RegulatoryChunker(chunk_size=200, document_title="DOC").chunk_text(text)
        ch1 = next(c for c in chunks if "premier chapitre" in c.content)
        ch2 = next(c for c in chunks if "second chapitre" in c.content)
        assert "Chapitre 1" in ch1.breadcrumb
        assert "Chapitre 2" not in ch1.breadcrumb
        assert "Chapitre 2" in ch2.breadcrumb
        # Chapitre 1 must not still be in scope after Chapitre 2 starts
        assert "Chapitre 1" not in ch2.breadcrumb

    def test_no_headings_yields_anonymous_section(self):
        text = "Just some plain text without any headings at all."
        chunks = RegulatoryChunker(chunk_size=200, document_title="DOC").chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].content == text
        # Breadcrumb is just the document title (no section path).
        assert chunks[0].breadcrumb == "DOC"

    def test_empty_text(self):
        assert RegulatoryChunker().chunk_text("") == []
        assert RegulatoryChunker().chunk_text("   \n\n  ") == []

    def test_numbered_section_depth_correct(self):
        # 4.2.1 should nest under 4.2 should nest under section "4"
        text = """4 Section principale
Texte 4.

4.2 Sous-section
Texte 4.2.

4.2.1 Sous-sous-section
Texte 4.2.1.
"""
        chunks = RegulatoryChunker(chunk_size=200, document_title="").chunk_text(text)
        deepest = next(c for c in chunks if "Texte 4.2.1" in c.content)
        assert "4 Section" in deepest.breadcrumb
        assert "4.2 Sous-section" in deepest.breadcrumb
        assert "4.2.1 Sous-sous-section" in deepest.breadcrumb
