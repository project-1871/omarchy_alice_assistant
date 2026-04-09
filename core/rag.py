"""
Local RAG (Retrieval-Augmented Generation) engine.
Uses ChromaDB + sentence-transformers (all-MiniLM-L6-v2) for semantic doc search.
Loads in a background thread so Alice starts instantly.
"""

import os
import threading
import json
import re
from pathlib import Path


class RAGEngine:
    """Semantic document search over Alice's memory/docs/ collection."""

    CHUNK_SIZE = 500    # characters per chunk
    CHUNK_OVERLAP = 60  # characters of overlap between chunks

    def __init__(self, db_dir: str, docs_dir: str):
        self.db_dir = db_dir
        self.docs_dir = docs_dir
        self._ready = False
        self._client = None
        self._collection = None
        self._lock = threading.Lock()

        # Load in background so Alice GUI starts immediately
        t = threading.Thread(target=self._init, daemon=True)
        t.start()

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Init ────────────────────────────────────────────────

    def _init(self):
        """Background init: load ChromaDB + embed model, then index any un-indexed docs."""
        try:
            import chromadb
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

            os.makedirs(self.db_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=self.db_dir)
            ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            collection = client.get_or_create_collection(
                name="alice_docs",
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )

            with self._lock:
                self._client = client
                self._collection = collection
                # _ready set AFTER indexing so searches see a complete DB

            # Index any docs not yet in the DB (model is loaded, this is fast)
            self._index_missing_docs()

            with self._lock:
                self._ready = True
            print("[RAG] ready — collection has", collection.count(), "chunks")

        except Exception as e:
            print(f"[RAG] init failed: {e}")

    def _index_missing_docs(self):
        """Index all docs in docs_dir that aren't already in the collection."""
        if not os.path.isdir(self.docs_dir):
            return

        indexed = self._get_indexed_sources()

        for filename in os.listdir(self.docs_dir):
            if not filename.endswith('.json'):
                continue
            name = filename[:-5]
            if name in indexed:
                continue
            doc_path = os.path.join(self.docs_dir, filename)
            try:
                with open(doc_path) as f:
                    doc = json.load(f)
                content = doc.get('content', '')
                doc_type = doc.get('type', 'text')
                if content.strip():
                    self.index_document(name, content, doc_type)
            except Exception as e:
                print(f"[RAG] failed to index {name}: {e}")

    def _get_indexed_sources(self) -> set:
        """Return set of source names already in the collection."""
        with self._lock:
            if not self._collection:
                return set()
            try:
                result = self._collection.get(include=['metadatas'])
                return {m['source'] for m in result['metadatas'] if 'source' in m}
            except Exception:
                return set()

    # ── Indexing ─────────────────────────────────────────────

    def index_document(self, name: str, content: str, doc_type: str = 'text'):
        """Chunk a document and add it to the vector store.
        Safe to call before _ready — will no-op if collection not set.
        """
        with self._lock:
            collection = self._collection
        if collection is None:
            return

        chunks = self._chunk(content)
        if not chunks:
            return

        ids = [f"{name}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [{'source': name, 'type': doc_type, 'chunk_idx': i}
                     for i in range(len(chunks))]
        try:
            collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        except Exception as e:
            print(f"[RAG] upsert error for {name}: {e}")

    def remove_document(self, name: str):
        """Remove all chunks for a document from the store."""
        with self._lock:
            collection = self._collection
        if collection is None:
            return
        try:
            collection.delete(where={"source": name})
        except Exception as e:
            print(f"[RAG] delete error for {name}: {e}")

    # ── Search ───────────────────────────────────────────────

    def search(self, query: str, n: int = 4) -> list[dict]:
        """Semantic search. Returns list of {source, content, type} dicts.

        Returns [] if not ready or on error.
        """
        with self._lock:
            collection = self._collection
        if not self._ready or collection is None:
            return []
        if not query.strip():
            return []

        try:
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(
                query_texts=[query],
                n_results=min(n, count),
                include=['documents', 'metadatas', 'distances'],
            )
            out = []
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            distances = results['distances'][0]
            for doc, meta, dist in zip(docs, metas, distances):
                out.append({
                    'source': meta.get('source', '?'),
                    'content': doc,
                    'type': meta.get('type', 'text'),
                    'distance': round(dist, 3),
                })
            return out
        except Exception as e:
            print(f"[RAG] search error: {e}")
            return []

    def format_context(self, query: str, n: int = 4) -> str:
        """Run search and return formatted context string for LLM injection.

        Returns empty string if nothing relevant found.
        """
        results = self.search(query, n=n)
        if not results:
            return ""

        lines = ["Relevant documentation:"]
        seen_sources = []
        for r in results:
            src = r['source']
            # Show source name once, nicely
            src_label = src.replace('_', ' ').replace('-', ' ')
            lines.append(f"\n[{src_label}]\n{r['content'].strip()}")
            if src not in seen_sources:
                seen_sources.append(src)

        return "\n".join(lines)

    # ── Chunking ─────────────────────────────────────────────

    def _chunk(self, text: str) -> list[str]:
        """Split text into overlapping chunks, respecting paragraph boundaries."""
        text = text.strip()
        if not text:
            return []

        # First split by double-newline (paragraphs/sections)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

        chunks = []
        current = ""

        for para in paragraphs:
            # If paragraph alone exceeds chunk size, hard-split it
            if len(para) > self.CHUNK_SIZE:
                if current:
                    chunks.append(current)
                    current = ""
                # Hard split the long paragraph
                for i in range(0, len(para), self.CHUNK_SIZE - self.CHUNK_OVERLAP):
                    chunk = para[i:i + self.CHUNK_SIZE]
                    if chunk.strip():
                        chunks.append(chunk)
                continue

            # Accumulate paragraphs into a chunk
            candidate = (current + "\n\n" + para).strip() if current else para
            if len(candidate) > self.CHUNK_SIZE:
                # Flush current, start new chunk with overlap
                if current:
                    chunks.append(current)
                # Use tail of current as overlap prefix
                overlap_start = max(0, len(current) - self.CHUNK_OVERLAP)
                overlap = current[overlap_start:] if current else ""
                current = (overlap + "\n\n" + para).strip()
            else:
                current = candidate

        if current:
            chunks.append(current)

        return [c for c in chunks if c.strip()]
