"""
RAG over kb/ files using TF-IDF cosine similarity.

No external vector DB needed. Index is built at startup and reused.
All answers cite the source KB file.
"""
import os
import math
import logging
import re
from collections import Counter
from typing import NamedTuple
from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL, KB_DIR

logger = logging.getLogger(__name__)


class Chunk(NamedTuple):
    text: str
    source: str    # relative path like "kb/rates.md"


class KBIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._tfidf: list[list[float]] = []
        self._build()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build(self) -> None:
        docs = [self._tokenize(c.text) for c in self.chunks]
        # Build vocabulary
        all_words = {w for doc in docs for w in doc}
        self._vocab = {w: i for i, w in enumerate(sorted(all_words))}
        n = len(docs)
        V = len(self._vocab)

        # IDF
        df = [0] * V
        for doc in docs:
            for w in set(doc):
                if w in self._vocab:
                    df[self._vocab[w]] += 1
        self._idf = [math.log((n + 1) / (d + 1)) + 1 for d in df]

        # TF-IDF vectors (L2-normalised)
        self._tfidf = []
        for doc in docs:
            tf = Counter(doc)
            vec = [0.0] * V
            for w, cnt in tf.items():
                if w in self._vocab:
                    i = self._vocab[w]
                    vec[i] = (cnt / len(doc)) * self._idf[i]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            self._tfidf.append([x / norm for x in vec])

    def query(self, question: str, top_k: int = 1) -> list[tuple[Chunk, float]]:
        """Return top_k (chunk, score) pairs sorted by cosine similarity."""
        tokens = self._tokenize(question)
        V = len(self._vocab)
        q_tf = Counter(tokens)
        q_vec = [0.0] * V
        for w, cnt in q_tf.items():
            if w in self._vocab:
                i = self._vocab[w]
                q_vec[i] = (cnt / len(tokens)) * self._idf[i]
        norm = math.sqrt(sum(x * x for x in q_vec)) or 1.0
        q_vec = [x / norm for x in q_vec]

        scores = []
        for idx, doc_vec in enumerate(self._tfidf):
            score = sum(a * b for a, b in zip(q_vec, doc_vec))
            scores.append((self.chunks[idx], score))
        return sorted(scores, key=lambda x: -x[1])[:top_k]


_index: KBIndex | None = None


def build_index() -> None:
    """Call once at startup to index all kb/ files."""
    global _index
    kb_path = KB_DIR
    if not os.path.isabs(kb_path):
        # Resolve relative to the backend directory
        kb_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "kb")
        kb_path = os.path.normpath(kb_path)

    chunks: list[Chunk] = []
    if not os.path.isdir(kb_path):
        logger.warning("KB directory not found: %s", kb_path)
        _index = KBIndex(chunks)
        return

    for fname in sorted(os.listdir(kb_path)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(kb_path, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Split into paragraphs
        paras = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]
        for para in paras:
            chunks.append(Chunk(text=para, source=f"kb/{fname}"))

    _index = KBIndex(chunks)
    logger.info("KB index built: %d chunks from %s", len(chunks), kb_path)


RETRIEVAL_THRESHOLD = 0.05   # minimum cosine score to use a chunk


def rag_answer(question: str) -> dict:
    """
    Retrieve best KB chunk and generate an answer with citation.
    Returns {answer, source} or {answer: None, source: None, refused: True}.
    """
    if _index is None:
        build_index()

    results = _index.query(question, top_k=3)
    results = [(c, s) for c, s in results if s >= RETRIEVAL_THRESHOLD]
    if not results:
        return {
            "answer": None,
            "source": None,
            "refused": True,
            "note": "Question is outside the knowledge base. Cannot answer.",
        }

    best_chunk, score = results[0]
    logger.debug("RAG: top score=%.3f source=%s", score, best_chunk.source)

    # Combine top chunks for richer context
    context_parts = [f"[{c.source}]\n{c.text}" for c, _ in results]
    context = "\n\n".join(context_parts)

    prompt = f"""You are a hotel assistant. Answer the question using ONLY the provided text.
If the text does not contain enough information, say you don't know.
Do not add information not present in the text.

Knowledge base:
{context}

Question: {question}
Answer:"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception("RAG LLM call failed: %s", exc)
        answer = best_chunk.text  # fallback: return raw chunk

    return {
        "answer": answer,
        "source": best_chunk.source,
        "refused": False,
    }
