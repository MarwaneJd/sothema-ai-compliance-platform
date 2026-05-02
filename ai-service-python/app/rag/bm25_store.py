import os
import pickle
import re
import unicodedata

import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger()

# Bump this when tokenization logic changes so on-disk pickles auto-rebuild.
BM25_INDEX_VERSION = 2

_TOKEN_RE = re.compile(r"[\w؀-ۿݐ-ݿ]+", re.UNICODE)
_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿ]")

# French stopwords with negations preserved (non, pas, aucun, ni, jamais, ne).
# Domain-specific high-frequency words added: article, selon, conformément,
# procédure, document — they appear in nearly every chunk and add no signal.
_FRENCH_STOPWORDS: frozenset[str] = frozenset(
    [
        "a", "à", "afin", "ai", "ainsi", "alors", "après", "au", "aucune",
        "aussi", "aux", "avant", "avec", "avoir", "c", "ce", "ceci", "cela",
        "ces", "cet", "cette", "ceux", "chaque", "comme", "d", "dans", "de",
        "des", "du", "dès", "elle", "elles", "en", "encore", "entre", "est",
        "et", "etc", "été", "être", "eux", "fait", "faire", "il", "ils",
        "j", "je", "l", "la", "le", "les", "leur", "leurs", "lui", "ma",
        "mais", "me", "mes", "moi", "mon", "même", "n", "ni", "nos", "notre",
        "nous", "on", "ont", "ou", "où", "par", "parce", "pas", "peu", "peut",
        "plus", "pour", "pourquoi", "puisque", "qu", "quand", "que", "quel",
        "quelle", "quelles", "quels", "qui", "quoi", "s", "sa", "sans", "se",
        "selon", "ses", "si", "sien", "son", "sont", "sous", "soit", "sur",
        "ta", "te", "tes", "toi", "ton", "tous", "tout", "toute", "toutes",
        "tu", "un", "une", "vos", "votre", "vous", "y", "été", "étant",
        "ayant", "ainsi", "autre", "autres",
        # Domain stoplist
        "article", "conformément", "document",
    ]
)

# Light Arabic stoplist — function words only.
_ARABIC_STOPWORDS: frozenset[str] = frozenset(
    [
        "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
        "التي", "الذي", "الذين", "هو", "هي", "هم", "أن", "إن", "أو", "أي",
        "كل", "بعض", "بين", "عند", "كما", "قد", "لقد", "ما", "لا", "لم",
        "لن", "كان", "كانت", "يكون", "تكون",
    ]
)

try:
    import Stemmer  # PyStemmer

    _FR_STEMMER = Stemmer.Stemmer("french")
except ImportError:  # pragma: no cover — fail-soft so dev install issues don't crash the service
    _FR_STEMMER = None
    logger.warning("PyStemmer not installed; French BM25 will not stem")

try:
    from pyarabic.araby import strip_tashkeel as _strip_tashkeel
except ImportError:  # pragma: no cover
    _strip_tashkeel = None
    logger.warning("PyArabic not installed; Arabic BM25 will not normalize diacritics")


def _strip_latin_diacritics(token: str) -> str:
    """NFKD-decompose then drop combining marks. Strips French accents
    (é → e, à → a, ç → c) without touching Arabic — combining marks on
    Arabic are tashkeel and need a different handler."""
    nfkd = unicodedata.normalize("NFKD", token)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_token(raw: str) -> str | None:
    """Single-token normalize. Returns None for tokens to drop."""
    if not raw:
        return None

    if _ARABIC_RE.search(raw):
        # Arabic branch: only strip tashkeel; never accent-fold.
        token = _strip_tashkeel(raw) if _strip_tashkeel else raw
        token = token.casefold()
        if token in _ARABIC_STOPWORDS or len(token) < 2:
            return None
        return token

    # Latin / French branch
    token = unicodedata.normalize("NFC", raw).casefold()
    if token in _FRENCH_STOPWORDS:
        return None
    folded = _strip_latin_diacritics(token)
    if folded in _FRENCH_STOPWORDS or len(folded) < 2:
        return None
    if _FR_STEMMER is not None:
        folded = _FR_STEMMER.stemWord(folded)
    return folded or None


def _tokenize_text(text: str) -> list[str]:
    """Public-by-convention helper — also used by tests."""
    raw_tokens = _TOKEN_RE.findall(text)
    out: list[str] = []
    for raw in raw_tokens:
        norm = _normalize_token(raw)
        if norm:
            out.append(norm)
    return out


class BM25Store:
    """BM25 keyword search index with serialization.

    Tokenization is multilingual-aware:
      - French/Latin: NFC casefold → strip diacritics → French Snowball stem
      - Arabic: strip tashkeel only (never accent-fold)
    Index pickles carry a version tag; mismatched versions are discarded
    so the index rebuilds on next ingest with the new tokenization.
    """

    def __init__(self) -> None:
        self.bm25: BM25Okapi | None = None
        self.corpus_ids: list[str] = []  # VectorStoreId strings, parallel to tokenized corpus
        self.corpus_texts: list[list[str]] = []  # Tokenized texts

    @property
    def size(self) -> int:
        return len(self.corpus_ids)

    def build_index(self, texts: list[str], vector_store_ids: list[str]) -> None:
        """Build a new BM25 index from texts and their VectorStoreIds."""
        tokenized = [self._tokenize(text) for text in texts]
        self.corpus_texts = tokenized
        self.corpus_ids = list(vector_store_ids)
        self.bm25 = BM25Okapi(tokenized)
        logger.info("BM25 index built", size=len(texts))

    def add_documents(self, texts: list[str], vector_store_ids: list[str]) -> None:
        """Add new documents and rebuild the index."""
        new_tokenized = [self._tokenize(text) for text in texts]
        self.corpus_texts.extend(new_tokenized)
        self.corpus_ids.extend(vector_store_ids)
        # BM25Okapi doesn't support incremental add, must rebuild
        self.bm25 = BM25Okapi(self.corpus_texts)
        logger.info("BM25 documents added", new_count=len(texts), total=len(self.corpus_ids))

    def remove_documents(self, vector_store_ids: set[str]) -> None:
        """Remove documents by VectorStoreId and rebuild index."""
        if not vector_store_ids:
            return

        filtered = [
            (text, vs_id)
            for text, vs_id in zip(self.corpus_texts, self.corpus_ids)
            if vs_id not in vector_store_ids
        ]

        if filtered:
            self.corpus_texts, self.corpus_ids = zip(*filtered)  # type: ignore[assignment]
            self.corpus_texts = list(self.corpus_texts)
            self.corpus_ids = list(self.corpus_ids)
            self.bm25 = BM25Okapi(self.corpus_texts)
        else:
            self.corpus_texts = []
            self.corpus_ids = []
            self.bm25 = None

        logger.info("BM25 documents removed", removed=len(vector_store_ids))

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search the BM25 index. Returns list of (VectorStoreId, BM25_score)."""
        if self.bm25 is None or not self.corpus_ids:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score descending
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :top_k
        ]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.corpus_ids[idx], float(scores[idx])))

        return results

    def load(self, path: str) -> None:
        """Load serialized BM25 index from disk.

        If the on-disk version doesn't match BM25_INDEX_VERSION, the index
        is discarded — callers will rebuild via add_documents on next ingest."""
        if not os.path.exists(path):
            logger.info("No existing BM25 index found")
            return
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            on_disk_version = data.get("version", 0) if isinstance(data, dict) else 0
            if on_disk_version != BM25_INDEX_VERSION:
                logger.warning(
                    "BM25 index version mismatch; discarding on-disk index",
                    on_disk=on_disk_version,
                    expected=BM25_INDEX_VERSION,
                )
                self.bm25 = None
                self.corpus_ids = []
                self.corpus_texts = []
                return
            self.corpus_texts = data["corpus_texts"]
            self.corpus_ids = data["corpus_ids"]
            if self.corpus_texts:
                self.bm25 = BM25Okapi(self.corpus_texts)
            logger.info("BM25 index loaded", size=len(self.corpus_ids))
        except Exception as e:
            logger.error("Failed to load BM25 index", error=str(e))
            self.bm25 = None
            self.corpus_ids = []
            self.corpus_texts = []

    def save(self, path: str) -> None:
        """Save BM25 index to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "version": BM25_INDEX_VERSION,
            "corpus_texts": self.corpus_texts,
            "corpus_ids": self.corpus_ids,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("BM25 index saved", size=len(self.corpus_ids))

    def _tokenize(self, text: str) -> list[str]:
        return _tokenize_text(text)
