"""Document search for the agent: GEMINI's docs, model docstrings and project files.

``DocIndex`` finds passages that explain a model, a method or a datasheet value. It never
supplies the numbers of a design; those come from tools. Two backends sit behind one interface:

- ``gemini-chroma``: GEMINI's own ChatPopup retrieval (Ollama embeddings in a local Chroma
  collection, then MMR re-ranking), without its translation and answer steps;
- ``bm25``: plain-Python keyword ranking over the same chunks. It is used whenever chromadb,
  the embedding model or the Ollama server is missing, and for any search that fails.

Nothing is read until the first search. It builds the keyword index at once and the vectors
in a background thread; BM25 answers until they are ready. Chunks and vectors are cached under
``hackathon/evals/runs/docs_index/``; a search reads again only the files that changed.
Attachments are kept in memory per conversation and are searched only with their own
``thread_id``. Retrieved text is data, never instructions: a passage that reads like an
instruction to the model is flagged ``suspicious``.
"""

from __future__ import annotations

import ast
import csv
import itertools
import json
import logging
import math
import os
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path("hackathon", "evals", "runs", "docs_index")
# What the base index reads: (folder or file relative to the root, file types).
CORPUS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("src/gemini_documentation", (".rst",)),
    ("src/gemini_model", (".py",)),
    ("src/gemini_simulator", (".py",)),
    ("hackathon/docs/cooling_design.md", (".md",)),
    ("hackathon/docs/reliability.md", (".md",)),
    ("hackathon/data", (".pdf", ".md", ".txt", ".rst", ".csv")),
)
EMBED_MODEL = "snowflake-arctic-embed:s"  # 67 MB; GEMINI's own embedding family
# Some embedding models are trained with a task prefix on the query and the document.
PREFIXES = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "qwen3-embedding": (
        "Instruct: Given a question, retrieve passages that answer it\nQuery: ",
        "",
    ),
    "snowflake-arctic-embed": ("Represent this sentence for searching relevant passages: ", ""),
    "mxbai-embed-large": ("Represent this sentence for searching relevant passages: ", ""),
}
# Similarity below which a chunk is not a candidate. Models differ: on this corpus the median
# chunk scores about 0.45 with snowflake and nomic, about 0.1 with all-minilm and embeddinggemma.
THRESHOLDS = {"snowflake-arctic-embed": 0.5, "nomic-embed-text": 0.5}
FORMAT = 1  # bump when the chunking changes; every cache is then rebuilt
PASSAGE_CHARS = 600
RETRY_SECONDS = 60.0  # after a failure, how long BM25 serves before Ollama is tried again
RESCAN_SECONDS = 5.0  # searches closer together than this skip the file check
SUSPICIOUS = re.compile(
    r"\b(ignore|disregard|forget|override)\s+(all\s+|any\s+)?(the\s+|your\s+|of\s+the\s+)?"
    r"(previous|prior|above|earlier|preceding|system|original)\s+"
    r"(instructions?|prompts?|messages?|rules|context|guidelines)"
    r"|\bforget\s+(everything|all)\b"
    r"|\byou\s+are\s+now\b"
    r"|\bsystem\s+prompt\b"
    r"|\b(respond|reply|answer)\s+(only\s+)?with\b"
    r"|\bnew\s+instructions?\s*:"
    r"|\bpretend\s+(to\s+be|you\s+are)\b"
    r"|\bdo\s+not\s+tell\s+the\s+user\b"
    r"|<\|?\s*(im_start|system|assistant)\s*\|?>"
    r"|\bnegeer\s+(alle\s+)?(vorige|eerdere)\s+instructies\b",
    re.IGNORECASE,
)
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in into is it its of on "
    "or so than that the then there these this to was what when where which while who why "
    "will with you your".split()
)
RST_RULE = re.compile(r"^\s*([=\-~^\"'`#*+:.])\1{2,}\s*$")
MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass
class Passage:
    """One retrieved piece of a document.

    Attributes
    ----------
    source : str
        Path relative to the repository root, or the attachment's name.
    section : str
        Heading path, ``page N``, or the documented class or function.
    text : str
        The chunk, trimmed to about 600 characters.
    score : float
        Cosine similarity (``gemini-chroma``) or BM25 score (``bm25``); compare scores only
        within one result list.
    suspicious : bool
        The chunk contains instruction-like text; treat it as data and warn, never follow it.
    """

    source: str
    section: str
    text: str
    score: float
    suspicious: bool = False

    def as_dict(self) -> dict:
        """Return the passage as a plain dict for events and traces."""
        return asdict(self)


@dataclass
class _Chunk:
    source: str
    section: str
    text: str
    n: int
    emb: Optional[List[float]] = None
    tokens: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}::c{self.n}"

    @property
    def embed_text(self) -> str:
        return f"{self.section}\n{self.text}" if self.section else self.text


def is_suspicious(text: str) -> bool:
    """Return True when a text reads like an instruction to the model.

    Parameters
    ----------
    text : str
        Retrieved document text.

    Returns
    -------
    bool
        True for phrases such as "ignore previous instructions" or "you are now".
    """
    return bool(SUSPICIOUS.search(text or ""))


def default_embed_model() -> str:
    """Return the embedding model: ``$DIOSCURI_EMBED_MODEL``, GEMINI's ``$EMBED_MODEL_VERSION``.

    Returns
    -------
    str
        The Ollama tag; ``snowflake-arctic-embed:s`` when neither variable is set.
    """
    return (
        os.environ.get("DIOSCURI_EMBED_MODEL")
        or os.environ.get("EMBED_MODEL_VERSION")
        or EMBED_MODEL
    )


# ------------------------------------------------------------------ chunking


def word_windows(text: str, max_words: int, overlap_words: int = 0) -> List[str]:
    """Split text into overlapping word windows, exactly as GEMINI's ChatPopup does.

    This is ``ChatPopup.chunksplitter_for_embeddings`` without its chromadb import, so both
    backends search the same chunks; a unit test checks that the two agree.

    Parameters
    ----------
    text : str
        Text to split.
    max_words : int
        Words per window.
    overlap_words : int
        Words shared by neighbouring windows.

    Returns
    -------
    list of str
        The windows, words joined by single spaces.
    """
    if max_words <= 0:
        return []
    if overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("overlap_words must be in [0, max_words)")
    words = re.findall(r"\S+", text)
    chunks = []
    step = max_words - overlap_words
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return chunks


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    """Return the BM25 terms of a text: lower case, split identifiers, no stop words, stemmed.

    Parameters
    ----------
    text : str
        Any text, including code identifiers such as ``HeatpumpBasic`` or ``Th_out``.

    Returns
    -------
    list of str
        The terms, in order.
    """
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text or "").lower()
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _trim(text: str, limit: int = PASSAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].rstrip() + " …"


# ------------------------------------------------------------- file readers


def _rst_inline(line: str) -> str:
    line = re.sub(r":[\w:+-]+:`([^`]*)`", r"\1", line)
    line = re.sub(r"`([^`<]*?)\s*<[^>]*>`__?", r"\1", line)
    return line.replace("``", "").replace("`", "")


def _rst_sections(text: str) -> List[Tuple[str, str]]:
    lines = text.splitlines()
    out, levels, stack, body = [], [], [], []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if RST_RULE.match(line):
            continue
        if line.strip() and not line.startswith(" ") and RST_RULE.match(nxt):
            out.append((" > ".join(stack[-2:]), "\n".join(body)))
            char = nxt.strip()[0]
            if char not in levels:
                levels.append(char)
            stack = stack[: levels.index(char)] + [_rst_inline(line.strip())]
            body = []
            continue
        s = line.strip()
        if re.match(r"^:[\w-]+:(\s|$)", s) or re.match(
            r"^\.\.\s+(_|\|?[\w-]*\|?\s*image|figure)", s
        ):
            continue
        s = re.sub(r"^\.\.\s+[\w-]+::\s*", "", s)
        s = re.sub(r"^[*-]\s+(-\s+)?", "", s)
        body.append(_rst_inline(s))
    out.append((" > ".join(stack[-2:]), "\n".join(body)))
    return out


def _md_sections(text: str) -> List[Tuple[str, str]]:
    out, stack, body, fenced = [], [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        heading = None if fenced else MD_HEADING.match(line)
        if heading:
            out.append((" > ".join(t for _, t in stack[-2:]), "\n".join(body)))
            level = len(heading.group(1))
            stack = [(lv, t) for lv, t in stack if lv < level] + [(level, heading.group(2))]
            body = []
            continue
        if re.match(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$", line) and "-" in line and "|" in line:
            continue
        line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
        body.append(re.sub(r"(\*\*|__|`|<!--.*?-->)", "", line).lstrip("> "))
    out.append((" > ".join(t for _, t in stack[-2:]), "\n".join(body)))
    return out


def _tex_plain(text: str) -> str:
    text = re.sub(r"\\(begin|end)\{[^{}]*\}(\[[^\]]*\])?(\{(?:[^{}]|\{[^{}]*\})*\})*", " ", text)
    text = re.sub(r"\\item\b", "\n- ", text)
    text = re.sub(r"(?<!\\)&", " | ", text).replace("\\\\", "\n")
    for _ in range(3):
        text = re.sub(r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)
    text = re.sub(r"\\([%&$#_{}])", r"\1", text)
    text = re.sub(r"\\[,;!: ]", " ", text).replace("~", " ").replace("---", "-")
    return text.replace("--", "-").replace("{", "").replace("}", "").replace("$", "")


def _tex_sections(text: str) -> List[Tuple[str, str]]:
    body = text.split("\\begin{document}", 1)[-1].split("\\end{document}", 1)[0]
    body = re.sub(r"(?<!\\)%.*", "", body)
    body = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", body, flags=re.S)
    parts = re.split(r"\\(?:sub)*section\*?\{((?:[^{}]|\{[^{}]*\})*)\}", body)
    pairs = [("front matter", parts[0])] + list(zip(parts[1::2], parts[2::2]))
    return [(_flat(_tex_plain(title)), _tex_plain(part)) for title, part in pairs]


def _py_sections(text: str, rel: str) -> List[Tuple[str, str]]:
    tree = ast.parse(text)
    module = re.sub(r"(^src/|/__init__\.py$|\.py$)", "", rel).replace("/", ".")
    out = []

    def keep(name: str, doc: Optional[str]) -> None:
        if doc and len(doc.split()) >= 5:
            out.append((name, "\n".join(ln for ln in doc.splitlines() if not RST_RULE.match(ln))))

    def visit(body, prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                keep(prefix + node.name, ast.get_docstring(node))
                if isinstance(node, ast.ClassDef):
                    visit(node.body, f"{prefix}{node.name}.")

    keep(module, ast.get_docstring(tree))
    visit(tree.body, "")
    return out


def _pdf_pages(path: Path) -> List[Tuple[int, str]]:
    """Return (page index, text) per page with GEMINI's loader, or pypdf when it is missing.

    A PDF exported from Word can come out one word per line (each word is its own text run);
    such a page is read again in pypdf's layout mode, which keeps the lines and the tables.
    """
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        from pypdf import PdfReader  # ImportError here means PDFs are skipped

        pages = [(i, page.extract_text() or "") for i, page in enumerate(PdfReader(path).pages)]
    else:
        docs = PyPDFLoader(str(path)).load()  # as ChatPopup.load_pdf_pages
        pages = [(int(d.metadata.get("page", 0)), d.page_content or "") for d in docs]
    if any(_word_per_line(text) for _, text in pages):
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages = [
            (i, _layout_text(reader.pages[i]) if _word_per_line(text) else text)
            for i, text in pages
        ]
    return pages


def _word_per_line(text: str) -> bool:
    """Return True for text broken into a word or two per line (a Word export's text runs)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return len(lines) >= 20 and sum(len(ln.split()) <= 2 for ln in lines) > 0.6 * len(lines)


def _layout_text(page) -> str:
    """Return a page's text in pypdf's layout mode, with its column padding squeezed."""
    try:
        text = page.extract_text(extraction_mode="layout") or ""
    except Exception:  # noqa: BLE001 - an older pypdf, or a page it can't lay out
        return page.extract_text() or ""
    return "\n".join(re.sub(r" {2,}", "  ", ln).strip() for ln in text.splitlines() if ln.strip())


def _csv_sections(path: Path) -> List[Tuple[str, str]]:
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(itertools.islice(csv.reader(fh), 3))
    if not rows:
        return []
    text = "Columns: " + ", ".join(rows[0])
    if rows[1:]:
        text += ". First rows: " + "; ".join(", ".join(r) for r in rows[1:])
    return [("columns", text)]


def _text_sections(name: str, text: str) -> List[Tuple[str, str]]:
    """Split a text by its kind, guessed from the file name."""
    kind = Path(name).suffix.lower()
    if kind == ".rst":
        return _rst_sections(text)
    if kind == ".md":
        return _md_sections(text)
    if kind == ".tex":
        return _tex_sections(text)
    if kind == ".py":
        try:
            return _py_sections(text, name)
        except SyntaxError:
            return [("", text)]
    pages = text.split("\f")
    if len(pages) > 1:
        return [(f"page {i + 1}", page) for i, page in enumerate(pages)]
    return [("", text)]


def read_sections(path: Path, name: str) -> List[Tuple[str, str]]:
    """Return a file's (section, text) pairs.

    Parameters
    ----------
    path : Path
        The file.
    name : str
        Its name in citations (decides the kind for text files).

    Returns
    -------
    list of tuple
        ``(section, text)``: headings for ``.rst``, ``.md`` and ``.tex``, the documented class or
        function for ``.py`` (docstrings only, read with ``ast``; nothing is imported),
        ``page N`` for PDFs and ``columns`` (header and two rows) for ``.csv``.
    """
    kind = path.suffix.lower()
    if kind == ".pdf":
        return [(f"page {page + 1}", text) for page, text in _pdf_pages(path)]
    if kind == ".csv":
        return _csv_sections(path)
    return _text_sections(name, path.read_text("utf-8", errors="replace"))


def _corpus_files(root: Path, corpus: Sequence[Tuple[str, Sequence[str]]]) -> Dict[str, Path]:
    files: Dict[str, Path] = {}
    for rel, kinds in corpus:
        base = root / rel
        found = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for path in found:
            name = path.relative_to(root).as_posix()
            hidden = any(p.startswith(".") or p == "__pycache__" for p in Path(name).parts)
            if path.is_file() and not hidden and path.suffix.lower() in kinds:
                files[name] = path
    # A PDF built from a LaTeX file next to it is read from its source (headings, no loader).
    return {n: p for n, p in files.items() if not (n.endswith(".pdf") and n[:-4] + ".tex" in files)}


# ---------------------------------------------------------------------- BM25


class _BM25:
    """An inverted index: term -> [(chunk number, term count)]."""

    def __init__(self, chunks: Sequence[_Chunk]):
        self.chunks = list(chunks)
        self.lengths = [len(c.tokens) for c in self.chunks]
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        for i, chunk in enumerate(self.chunks):
            for term, count in Counter(chunk.tokens).items():
                self.postings[term].append((i, count))


def _bm25_rank(
    query: List[str], indexes: Sequence[_BM25], k1: float = 1.5, b: float = 0.75
) -> List[Tuple[float, _Chunk]]:
    """Score every chunk of several indexes with one shared set of term statistics."""
    n = sum(len(ix.chunks) for ix in indexes)
    avgdl = sum(sum(ix.lengths) for ix in indexes) / max(n, 1) or 1.0
    scores: Dict[Tuple[int, int], float] = defaultdict(float)
    for term, qtf in Counter(query).items():
        df = sum(len(ix.postings.get(term, ())) for ix in indexes)
        if not df:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for p, ix in enumerate(indexes):
            for i, tf in ix.postings.get(term, ()):
                norm = tf + k1 * (1 - b + b * ix.lengths[i] / avgdl)
                scores[(p, i)] += qtf * idf * tf * (k1 + 1) / norm
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(score, indexes[p].chunks[i]) for (p, i), score in ranked]


# ------------------------------------------------------- GEMINI's ChatPopup


class _FixedOptions:
    """An Ollama client that sends the same options with every embedding call."""

    def __init__(self, host: str, options: dict, timeout: float):
        from ollama import Client

        self._client = Client(host=host, timeout=timeout)
        self.options = dict(options)

    def embed(self, model: str, input, **kwargs):
        return self._client.embed(model=model, input=input, options=self.options)

    def embeddings(self, model: str, prompt: str, **kwargs):
        return {"embedding": self.embed(model, [prompt])["embeddings"][0]}


_STORE = None


def _store_class():
    """Return GEMINI's ChatPopup subclassed for a local folder; raise ImportError without it."""
    global _STORE
    if _STORE is not None:
        return _STORE
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        import chromadb
        from chromadb.config import Settings

        from gemini_application.chatpopup.chatpopup import ChatPopup
    finally:  # ChatPopup's module calls logging.basicConfig on import; undo that
        root.handlers[:] = handlers
        root.setLevel(level)

    class GeminiStore(ChatPopup):
        """ChatPopup's embedding, Chroma query and MMR re-ranking on a local folder.

        Its translation and LLM answer steps are never called. Ingestion follows
        ``ChatPopup.update_data`` (a manifest of file signatures, delete and re-add changed
        files) but takes chunks from ``DocIndex`` so both backends search the same text.
        """

        def __init__(self, folder: Path, model: str, host: str, options: dict, version: str):
            """Open (or create) the collection for this embedding model."""
            super().__init__()
            slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-")
            self.chromadb_use_http = False
            self.chroma_dir = str(folder / "chroma")
            self.docs_dir = str(folder)  # where ChatPopup keeps its manifest
            self.manifest_filename = f"chroma-{slug}.json"
            self.collection_name = f"dioscuri-docs-{slug}"
            self.ollama_embeddings_model = model
            self.retrieve_candidates = 24
            self.mmr_lambda = 0.75
            self.embedding_batch_size = 16
            self.host, self.options, self.version = host, options, version
            family = next((p for p in PREFIXES if model.startswith(p)), None)
            self.query_prefix, self.doc_prefix = PREFIXES.get(family, ("", ""))
            self.similarity_threshold = THRESHOLDS.get(family, 0.3)
            folder.mkdir(parents=True, exist_ok=True)
            self.initialize_model()
            manifest = self.load_manifest()
            self.known = dict(manifest["files"]) if manifest.get("version") == version else {}
            if not self.known or not self.chroma_collection.count():
                self.reset()

        def _build_ollama_client(self):
            return _FixedOptions(self.host, self.options, timeout=120)

        def _build_chroma_client(self):
            settings = Settings(anonymized_telemetry=False)  # fully local: no telemetry
            return chromadb.PersistentClient(path=self.chroma_dir, settings=settings)

        def reset(self) -> None:
            """Drop every vector (a new chunking format or a lost folder)."""
            self.delete_collection()
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )
            self.known = {}

        def get_embedding(self, user_message: str) -> List[float]:
            """Embed a query with the model's query prefix."""
            return self.embed_one_ollama(self.query_prefix + user_message)

        def embed_chunks(self, chunks: Sequence[_Chunk]) -> List[List[float]]:
            """Embed chunks (section heading and text) with the model's document prefix."""
            embs = self.get_embedding_list([self.doc_prefix + c.embed_text for c in chunks])
            if len(embs) != len(chunks) or not all(len(e) for e in embs):
                raise RuntimeError("the embedding model returned empty vectors")
            return embs

        def sync(self, files: Dict[str, Tuple[list, List[_Chunk]]]) -> int:
            """Embed new or changed files and drop removed ones; return the chunks embedded."""
            for rel in [r for r in self.known if r not in files]:
                self.chroma_collection.delete(where={"source": rel})
                self.known.pop(rel)
            todo = [rel for rel, (sig, _) in files.items() if self.known.get(rel) != sig]
            done = 0
            for i in range(0, len(todo), 8):  # save progress every few files
                batch = todo[i : i + 8]
                chunks = [c for rel in batch for c in files[rel][1]]
                for rel in batch:
                    self.chroma_collection.delete(where={"source": rel})
                if chunks:
                    embs = self.embed_chunks(chunks)
                    step = max(1, int(self.chroma_add_batch_size))
                    for j in range(0, len(chunks), step):
                        part = chunks[j : j + step]
                        self.chroma_collection.add(
                            ids=[c.id for c in part],
                            documents=[c.text for c in part],
                            embeddings=embs[j : j + step],
                            metadatas=[
                                {"source": c.source, "section": c.section, "chunk": c.n}
                                for c in part
                            ],
                        )
                for rel in batch:
                    self.known[rel] = files[rel][0]
                self.save_manifest({"version": self.version, "files": self.known})
                done += len(chunks)
            return done

        def retrieve(self, query: str, k: int, extra: Sequence[_Chunk]) -> List[Passage]:
            """Return the top ``k`` passages: Chroma query, threshold, then MMR re-ranking."""
            query_emb = self.get_embedding(query)
            if not query_emb:
                raise RuntimeError("empty query embedding")
            candidates = []
            count = self.chroma_collection.count()
            if count:
                context = self.chroma_collection.query(
                    query_embeddings=[query_emb],
                    n_results=min(int(self.retrieve_candidates), count),
                    include=["documents", "metadatas", "distances", "embeddings"],
                )
                found = self.filter_context(context)
                candidates = [
                    {"doc": d, "meta": m, "id": i, "sim": s, "emb": list(e)}
                    for d, m, i, s, e in zip(
                        found["documents"],
                        found["metadatas"],
                        found["ids"],
                        found["similarities"],
                        found["embeddings"],
                    )
                ]
            missing = [c for c in extra if c.emb is None]
            if missing:
                for chunk, emb in zip(missing, self.embed_chunks(missing)):
                    chunk.emb = list(emb)
            for chunk in extra:
                sim = self.cosine_sim(query_emb, chunk.emb)
                if sim >= float(self.similarity_threshold):
                    meta = {"source": chunk.source, "section": chunk.section}
                    candidates.append(
                        {
                            "doc": chunk.text,
                            "meta": meta,
                            "id": chunk.id,
                            "sim": sim,
                            "emb": chunk.emb,
                        }
                    )
            selected = self.mmr_rerank(query_emb, candidates, top_k=k, lam=float(self.mmr_lambda))
            return [
                Passage(
                    source=c["meta"].get("source", ""),
                    section=c["meta"].get("section", ""),
                    text=_trim(c["doc"]),
                    score=round(float(c["sim"]), 4),
                    suspicious=is_suspicious(c["doc"]),
                )
                for c in selected
            ]

    _STORE = GeminiStore
    return _STORE


# ------------------------------------------------------------------- the index


class DocIndex:
    """Searchable documents: a lazily built base corpus plus per-conversation attachments.

    Thread-safe: searches, attachments and refreshes may come from several threads. The vectors
    are built in a background thread by default; searches use BM25 until they are ready.

    Parameters
    ----------
    root : str or Path, optional
        Repository root that ``corpus`` paths are relative to; defaults to this checkout.
    corpus : sequence of (str, tuple of str), optional
        Folders or files and the file types read from them; defaults to ``CORPUS``.
    cache_dir : str or Path, optional
        Where chunks and vectors are cached; defaults to
        ``<root>/hackathon/evals/runs/docs_index``.
    backend : {"auto", "gemini-chroma", "bm25"}
        ``auto`` and ``gemini-chroma`` use GEMINI's Chroma retrieval when it works and BM25
        otherwise (neither raises); ``bm25`` never contacts Ollama.
    embed_model : str, optional
        Ollama embedding model; defaults to ``default_embed_model()``.
    host : str, optional
        Ollama server URL; defaults to ``$OLLAMA_HOST`` or the local server.
    device : {"auto", "cpu"}
        ``"cpu"`` keeps the embedding model on the CPU with ``num_thread`` threads.
    num_thread : int
        CPU threads when ``device="cpu"``.
    background : bool
        Embed in a background thread (searches use BM25 meanwhile). ``False`` makes a refresh
        wait for the vectors, which tests and evals want.
    chunk_words, overlap_words : int
        Word window and overlap of a chunk (about 600 characters for 100 words).
    """

    def __init__(
        self,
        root=None,
        corpus: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
        cache_dir=None,
        backend: str = "auto",
        embed_model: Optional[str] = None,
        host: Optional[str] = None,
        device: str = "auto",
        num_thread: int = 8,
        background: bool = True,
        chunk_words: int = 100,
        overlap_words: int = 20,
    ):
        """Configure the index; nothing is read or loaded until the first search."""
        if backend not in ("auto", "gemini-chroma", "bm25"):
            raise ValueError(f"unknown backend {backend!r}")
        self.root = Path(root) if root else ROOT
        self.corpus = tuple(corpus or CORPUS)
        self.cache_dir = Path(cache_dir) if cache_dir else self.root / CACHE
        self.backend = backend
        self.embed_model = embed_model or default_embed_model()
        self.host = host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
        # Fixed options: changing num_ctx, num_gpu or num_thread would reload the model.
        self.options: dict = {"num_ctx": 512}
        if device == "cpu":
            self.options.update(num_gpu=0, num_thread=num_thread)
        self.background = background
        self.rescan_seconds = RESCAN_SECONDS
        self.chunk_words, self.overlap_words = chunk_words, overlap_words
        self.version = f"{FORMAT}-{chunk_words}-{overlap_words}"
        self._lock = threading.RLock()  # corpus, chunks, attachments, state
        self._store_lock = threading.Lock()  # GEMINI's store: one user at a time
        self._files: Dict[str, dict] = {}
        self._loaded = False
        self._scanned = -math.inf
        self._chunks: List[_Chunk] = []
        self._by_source: Dict[str, List[_Chunk]] = {}
        self._bm25: Optional[_BM25] = None
        self._store = None
        self._ready = False
        self._syncing: Optional[threading.Thread] = None
        self._retry_at = 0.0
        self._reason = ""
        self._threads: Dict[str, Dict[str, List[_Chunk]]] = {}
        self._stats: dict = {"build_seconds": None, "embed_seconds": None, "embedded_chunks": 0}

    # ----------------------------------------------------------------- public

    def search(
        self,
        query: str,
        k: int = 4,
        thread_id: Optional[str] = None,
        only_attached: bool = False,
        project: Optional[str] = None,
    ) -> List[Passage]:
        """Return the ``k`` passages that best match a query.

        The first call builds the keyword index (reading only files that changed since the
        cache was written) and starts the vectors; later calls re-check file signatures
        (about 15 ms) at most every ``rescan_seconds``.

        Parameters
        ----------
        query : str
            What to look for, in plain words.
        k : int
            Passages to return at most.
        thread_id : str, optional
            Also search this conversation's attachments (never another conversation's).
        only_attached : bool
            Search only this conversation's attachments (keywords; when no word matches, their
            first passages), for questions about an attached file.
        project : str, optional
            Also search the documents added under this key (a project's own documents, shared
            by its conversations; never searched as attachments).

        Returns
        -------
        list of Passage
            Best first; empty when nothing matches.
        """
        if time.monotonic() - self._scanned >= self.rescan_seconds:
            self.refresh()  # outside the lock: it may wait for the embedding thread
        with self._lock:
            extra = [c for chunks in self._threads.get(thread_id, {}).values() for c in chunks]
            if only_attached:
                return self._attached_search(query, k, extra)
            if project:
                extra += [c for chunks in self._threads.get(project, {}).values() for c in chunks]
            tic = time.perf_counter()
            hits = None
            # A store busy embedding changed files is not waited for: BM25 answers instead.
            if self._ready and self._store_lock.acquire(blocking=False):
                try:
                    hits = self._store.retrieve(query, k, extra)
                except Exception as err:  # Ollama stopped, model removed: keyword search
                    self._fall_back(f"search failed: {type(err).__name__}: {err}")
                finally:
                    self._store_lock.release()
            self._stats["last_backend"] = "bm25" if hits is None else "gemini-chroma"
            if hits is None:
                hits = self._keyword_search(query, k, extra)
            self._stats["query_seconds"] = round(time.perf_counter() - tic, 4)
            return hits

    def add_text(self, thread_id: str, name: str, text: str) -> int:
        """Attach a document to one conversation; adding the same name again replaces it.

        Parameters
        ----------
        thread_id : str
            The conversation.
        name : str
            File name as cited; its extension picks the splitter (``.md``, ``.rst``, ``.tex``,
            ``.py``; form feeds split pages of plain text).
        text : str
            The document's text.

        Returns
        -------
        int
            Chunks added.
        """
        chunks = self._chunk(name, _text_sections(name, text))
        with self._lock:
            self._threads.setdefault(thread_id, {})[name] = chunks
        return len(chunks)

    def add_file(self, thread_id: str, path, name: Optional[str] = None) -> int:
        """Attach a file to one conversation, read like the base corpus (PDF pages, CSV header).

        Parameters
        ----------
        thread_id : str
            The conversation.
        path : str or Path
            The file.
        name : str, optional
            Name in citations; defaults to the file name.

        Returns
        -------
        int
            Chunks added.

        Raises
        ------
        ImportError
            For a PDF when neither langchain-community nor pypdf is installed.
        """
        path = Path(path)
        name = name or path.name
        chunks = self._chunk(name, read_sections(path, name))
        with self._lock:
            self._threads.setdefault(thread_id, {})[name] = chunks
        return len(chunks)

    def drop_thread(self, thread_id: str) -> None:
        """Forget a conversation's attachments."""
        with self._lock:
            self._threads.pop(thread_id, None)

    def info(self) -> dict:
        """Return the index state; this never builds anything.

        Returns
        -------
        dict
            ``built``; ``backend``: what the next search uses (``gemini-chroma``, ``bm25``, or
            None before the first build); ``building`` (vectors being embedded);
            ``embedding_model`` (None for BM25); ``fallback_reason``; ``n_chunks``;
            ``n_files``; ``build_seconds`` (first keyword build); ``embed_seconds`` and
            ``embedded_chunks`` (last vector update); ``refresh_seconds`` and
            ``changed_files`` (last refresh: files read again or removed); ``query_seconds``
            and ``last_backend`` (last search); ``sources`` (chunks per file); ``skipped``
            (unreadable files); ``threads`` (attached chunks per conversation); ``cache_dir``
            and ``host``.
        """
        with self._lock:
            built = self._loaded
            backend = ("gemini-chroma" if self._ready else "bm25") if built else None
            return {
                "built": built,
                "backend": backend,
                "building": self._syncing is not None,
                "requested": self.backend,
                "embedding_model": self.embed_model if self._ready else None,
                "fallback_reason": self._reason or None,
                "n_chunks": len(self._chunks),
                "n_files": sum(1 for f in self._files.values() if f.get("chunks")),
                **self._stats,
                "sources": {
                    rel: len(f["chunks"]) for rel, f in self._files.items() if f.get("chunks")
                },
                "skipped": {rel: f["error"] for rel, f in self._files.items() if f.get("error")},
                "threads": {t: sum(map(len, d.values())) for t, d in self._threads.items()},
                "cache_dir": str(self.cache_dir),
                "host": self.host,
            }

    def refresh(self, wait: Optional[bool] = None) -> dict:
        """Build the index, or bring it up to date with the files; return ``info()``.

        Parameters
        ----------
        wait : bool, optional
            Wait for the vectors; defaults to ``not background``. Calling ``refresh()`` at
            start-up warms the index without blocking.

        Returns
        -------
        dict
            The index state after the refresh.
        """
        wait = (not self.background) if wait is None else wait
        with self._lock:
            tic = time.perf_counter()
            first = not self._loaded
            changed = self._read_corpus()
            if changed or first:
                self._chunks = [
                    self._make_chunk(rel, *item, n)
                    for rel, f in sorted(self._files.items())
                    for n, item in enumerate(f.get("chunks", []))
                ]
                self._bm25 = _BM25(self._chunks)
                self._by_source = defaultdict(list)
                for chunk in self._chunks:
                    self._by_source[chunk.source].append(chunk)
            seconds = round(time.perf_counter() - tic, 3)
            if first:
                self._stats["build_seconds"] = seconds
            self._stats.update(refresh_seconds=seconds, changed_files=changed)
            self._scanned = time.monotonic()
            job = self._start_sync(changed or first, wait)
        if job is not None and wait:
            job.join()
        return self.info()

    # ---------------------------------------------------------------- private

    def _make_chunk(self, source: str, section: str, text: str, n: int) -> _Chunk:
        stem = re.sub(r"[_./-]+", " ", Path(source).stem)
        return _Chunk(source, section, text, n, tokens=tokenize(f"{stem} {section} {text}"))

    def _windows(self, sections: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
        return [
            (_flat(section), window)
            for section, text in sections
            for window in word_windows(_flat(text), self.chunk_words, self.overlap_words)
        ]

    def _chunk(self, name: str, sections: Sequence[Tuple[str, str]]) -> List[_Chunk]:
        return [self._make_chunk(name, s, t, n) for n, (s, t) in enumerate(self._windows(sections))]

    def _manifest_path(self) -> Path:
        return self.cache_dir / "chunks.json"

    def _read_corpus(self) -> int:
        """Re-read new or changed files and drop removed ones; return how many changed."""
        if not self._loaded:
            try:
                data = json.loads(self._manifest_path().read_text("utf-8"))
                if data.get("version") == self.version:
                    self._files = data["files"]
            except (OSError, ValueError, KeyError):
                self._files = {}
            self._loaded = True
        found = _corpus_files(self.root, self.corpus)
        changed = 0
        for rel in [r for r in self._files if r not in found]:
            del self._files[rel]
            changed += 1
        for rel, path in found.items():
            stat = path.stat()
            sig = [stat.st_mtime_ns, stat.st_size]
            if self._files.get(rel, {}).get("sig") == sig:
                continue
            changed += 1
            try:
                self._files[rel] = {"sig": sig, "chunks": self._windows(read_sections(path, rel))}
            except Exception as err:  # unreadable file or missing PDF reader: skip it
                self._files[rel] = {"sig": sig, "chunks": [], "error": f"{type(err).__name__}"}
                logger.warning("docs: skipped %s (%s)", rel, err)
        if changed:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            keep = {r: f for r, f in self._files.items() if not f.get("error")}
            tmp = self._manifest_path().with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": self.version, "files": keep}), "utf-8")
            tmp.replace(self._manifest_path())
        return changed

    def _start_sync(self, changed: bool, wait: bool) -> Optional[threading.Thread]:
        """Start updating GEMINI's store when files changed or a retry is due (under the lock)."""
        if self.backend == "bm25" or self._syncing is not None:
            return self._syncing
        if self._ready and not changed:
            return None
        if not self._ready and time.monotonic() < self._retry_at:
            return None
        files = {
            rel: (f["sig"], self._by_source.get(rel, []))
            for rel, f in self._files.items()
            if not f.get("error")
        }
        self._syncing = threading.Thread(target=self._sync, args=(files,), daemon=True)
        if wait:
            self._sync(files)
            return None
        self._syncing.start()
        return self._syncing

    def _sync(self, files: Dict[str, Tuple[list, List[_Chunk]]]) -> None:
        """Open GEMINI's store and embed what changed; any failure means BM25 for a while."""
        tic = time.perf_counter()
        error = None
        embedded = 0
        with self._store_lock:
            try:
                if self._store is None:
                    self._store = _store_class()(
                        self.cache_dir, self.embed_model, self.host, self.options, self.version
                    )
                embedded = self._store.sync(files)
                if not self._ready:
                    self._store.get_embedding("warm up")  # proves the model answers
            except Exception as err:
                error = err
        with self._lock:
            self._syncing = None
            if error is not None:
                reason = f"{type(error).__name__}: {error}"
                self._fall_back(reason, forever=isinstance(error, ImportError))
                return
            self._ready, self._reason = True, ""
            self._stats.update(
                embed_seconds=round(time.perf_counter() - tic, 3), embedded_chunks=embedded
            )

    def _fall_back(self, reason: str, forever: bool = False) -> None:
        if self._ready or reason != self._reason:
            logger.warning("docs: using BM25 (%s)", reason)
        self._ready, self._reason = False, reason
        self._retry_at = math.inf if forever else time.monotonic() + RETRY_SECONDS

    def _attached_search(self, query: str, k: int, extra: Sequence[_Chunk]) -> List[Passage]:
        if not extra:
            return []
        terms = tokenize(query)
        ranked = [(s, c) for s, c in _bm25_rank(terms, [_BM25(extra)]) if s > 0] if terms else []
        chosen = ranked[:k] or [(0.0, c) for c in extra[:k]]
        return [
            Passage(
                source=c.source,
                section=c.section,
                text=_trim(c.text),
                score=round(score, 3),
                suspicious=is_suspicious(c.text),
            )
            for score, c in chosen
        ]

    def _keyword_search(self, query: str, k: int, extra: Sequence[_Chunk]) -> List[Passage]:
        terms = tokenize(query)
        if not terms or self._bm25 is None:
            return []
        indexes = [self._bm25] + ([_BM25(extra)] if extra else [])
        return [
            Passage(
                source=c.source,
                section=c.section,
                text=_trim(c.text),
                score=round(score, 3),
                suspicious=is_suspicious(c.text),
            )
            for score, c in _bm25_rank(terms, indexes)[:k]
        ]
