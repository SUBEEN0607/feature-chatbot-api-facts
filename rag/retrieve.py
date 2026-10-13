"""Top-k retrieval over doc_chunk. pgvector cosine on Postgres; numpy cosine on SQLite."""
from __future__ import annotations

import numpy as np
from sqlalchemy import select

from db.models import EMBED_DIM, DocChunk
from db.session import get_engine, session_factory

from .embed import get_embedder


def pg_query(q, embed_model: str, k: int):
    """pgvector cosine distance (<=>). Built with op() because DocChunk.embedding is a dialect-switching
    TypeDecorator, which does not expose pgvector's comparator methods."""
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Float, bindparam

    qv = bindparam("qvec", [float(x) for x in q], type_=Vector(EMBED_DIM))
    dist = DocChunk.embedding.op("<=>", return_type=Float)(qv)
    return (select(DocChunk, dist.label("d")).where(DocChunk.embed_model == embed_model)
            .order_by(dist).limit(k))


def retrieve(query: str, k: int = 5, engine=None, embedder=None, doc_prefixes: tuple[str, ...] | None = None) -> list[dict]:
    """Top-k chunks. doc_prefixes restricts to documents whose doc_id starts with one of them
    (e.g. evidence only: ('rag/corpus/', 'ontology/sources.csv'))."""
    engine = engine or get_engine()
    emb = embedder or get_embedder()
    q = np.asarray(emb.query(query), dtype=np.float32)
    with session_factory(engine)() as s:
        if engine.dialect.name == "postgresql":
            stmt = pg_query(q, emb.name, k)
            if doc_prefixes:
                from sqlalchemy import or_
                stmt = stmt.where(or_(*[DocChunk.doc_id.startswith(pfx) for pfx in doc_prefixes]))
            rows = s.execute(stmt).all()
            hits = [(c, 1.0 - float(d)) for c, d in rows]
        else:
            chunks = [c for c in s.scalars(select(DocChunk).where(DocChunk.embed_model == emb.name))
                      if not doc_prefixes or c.doc_id.startswith(doc_prefixes)]
            if not chunks:
                return []
            m = np.asarray([c.embedding for c in chunks], dtype=np.float32)
            m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-12
            scores = m @ (q / (np.linalg.norm(q) + 1e-12))
            top = np.argsort(-scores)[:k]
            hits = [(chunks[i], float(scores[i])) for i in top]
    return [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "source_id": c.source_id, "title": c.title,
             "section": c.section, "text": c.text, "score": round(sc, 4)} for c, sc in hits]
