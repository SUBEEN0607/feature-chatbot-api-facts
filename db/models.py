"""SQLAlchemy models. One schema for Postgres + pgvector (compose) and a local SQLite file (tests).

Natural keys everywhere a natural key exists, so `session.merge` makes every load an upsert.
`db/schema.sql` is generated from this file (`python -m db.schema_sql`); a test keeps them equal.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

EMBED_DIM = 384  # intfloat/multilingual-e5-small; the hash test embedder uses the same size


class Embedding(TypeDecorator):
    """pgvector `vector(384)` on Postgres; a JSON list on SQLite (cosine done in numpy)."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(EMBED_DIM))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(v) for v in value]

    def process_result_value(self, value, dialect):
        return None if value is None else [float(v) for v in value]


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class Industry(Base):
    __tablename__ = "industry"
    industry_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    label_ko: Mapped[str | None] = mapped_column(String(100))
    config: Mapped[dict | None]            # industry/<x>.yaml as loaded
    meta: Mapped[dict | None]              # district_profile meta + survival tables


class Source(Base):
    __tablename__ = "source"
    source_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    publisher_author: Mapped[str | None] = mapped_column(Text)
    year: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(String(40))
    reliability_note: Mapped[str | None] = mapped_column(Text)


class Criterion(Base):
    __tablename__ = "criterion"
    criterion_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    industry_id: Mapped[str | None] = mapped_column(ForeignKey("industry.industry_id"))
    name_ko: Mapped[str | None] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40))
    driver_node: Mapped[str | None] = mapped_column(String(60))   # parent in the driver tree
    unit: Mapped[str | None] = mapped_column(String(40))
    data_type: Mapped[str | None] = mapped_column(String(20))
    method: Mapped[str | None] = mapped_column(String(20))        # public | guesstimate | interview_later | derived
    source_ids: Mapped[str | None] = mapped_column(String(200))   # ';'-separated, as in sources.csv
    industry_scope: Mapped[str | None] = mapped_column(String(20))
    in_sim: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class CriterionEdge(Base):
    __tablename__ = "criterion_edge"
    from_id: Mapped[str] = mapped_column(ForeignKey("criterion.criterion_id"), primary_key=True)
    to_id: Mapped[str] = mapped_column(ForeignKey("criterion.criterion_id"), primary_key=True)
    sign: Mapped[str | None] = mapped_column(String(4))
    mechanism_ko: Mapped[str | None] = mapped_column(Text)
    source_ids: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[str | None] = mapped_column(String(4))


class District(Base):
    __tablename__ = "district"
    trdar_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    industry_id: Mapped[str | None] = mapped_column(ForeignKey("industry.industry_id"))
    trdar_name: Mapped[str | None] = mapped_column(String(100))
    trdar_type: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str | None] = mapped_column(String(10))           # primary | fringe
    adstrd_name: Mapped[str | None] = mapped_column(String(40))
    signgu_name: Mapped[str | None] = mapped_column(String(40))
    area_m2: Mapped[float | None] = mapped_column(Float)
    centroid_lon: Mapped[float | None] = mapped_column(Float)
    centroid_lat: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[dict | None]          # GeoJSON (WGS84)
    summary: Mapped[dict | None]           # sbiz counts, license counts, match counts, annual rollups


class DistrictQuarter(Base):
    __tablename__ = "district_quarter"
    trdar_code: Mapped[str] = mapped_column(ForeignKey("district.trdar_code"), primary_key=True)
    quarter: Mapped[str] = mapped_column(String(5), primary_key=True)
    hansik_sales_krw: Mapped[float | None] = mapped_column(Float)      # per QUARTER
    hansik_sales_count: Mapped[float | None] = mapped_column(Float)
    avg_ticket_krw: Mapped[float | None] = mapped_column(Float)
    stores_total: Mapped[int | None] = mapped_column(Integer)
    stores_independent: Mapped[int | None] = mapped_column(Integer)
    stores_franchise: Mapped[int | None] = mapped_column(Integer)
    stores_opened: Mapped[int | None] = mapped_column(Integer)
    stores_closed: Mapped[int | None] = mapped_column(Integer)
    sales_per_store_month_krw: Mapped[float | None] = mapped_column(Float)
    evening_share_17_24: Mapped[float | None] = mapped_column(Float)
    lunch_share_11_14: Mapped[float | None] = mapped_column(Float)
    weekend_share: Mapped[float | None] = mapped_column(Float)
    flpop_total: Mapped[float | None] = mapped_column(Float)
    workers_total: Mapped[float | None] = mapped_column(Float)
    residents_total: Mapped[float | None] = mapped_column(Float)
    households_total: Mapped[float | None] = mapped_column(Float)
    shares: Mapped[dict | None]            # dow / timeband / age / sex / flpop shares, facilities


class Store(Base):
    """Public 소상공인 stores inside the study 상권 (I20107 primary, comparison and context rows)."""
    __tablename__ = "store"
    store_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    trdar_code: Mapped[str | None] = mapped_column(ForeignKey("district.trdar_code"))
    name: Mapped[str | None] = mapped_column(String(200))
    branch_name: Mapped[str | None] = mapped_column(String(100))
    class_code: Mapped[str | None] = mapped_column(String(10))
    class_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(12))
    franchise_flag: Mapped[bool | None] = mapped_column(Boolean)
    road_addr: Mapped[str | None] = mapped_column(Text)
    floor: Mapped[str | None] = mapped_column(String(20))
    lon: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)
    snapshot: Mapped[str | None] = mapped_column(String(8))
    license_id: Mapped[str | None] = mapped_column(String(40))       # best match, see match_confidence
    match_confidence: Mapped[str | None] = mapped_column(String(14))
    match_name_score: Mapped[float | None] = mapped_column(Float)
    match_dist_m: Mapped[float | None] = mapped_column(Float)


class StoreLicense(Base):
    """일반음식점 인허가 rows inside the study 상권: the survival label."""
    __tablename__ = "store_license"
    license_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    trdar_code: Mapped[str | None] = mapped_column(ForeignKey("district.trdar_code"))
    name: Mapped[str | None] = mapped_column(String(200))
    uptae: Mapped[str | None] = mapped_column(String(40))
    hansik: Mapped[bool | None] = mapped_column(Boolean)
    pork_name_hint: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str | None] = mapped_column(String(20))
    open_date: Mapped[datetime | None] = mapped_column(Date)
    close_date: Mapped[datetime | None] = mapped_column(Date)
    censor_date: Mapped[datetime | None] = mapped_column(Date)
    months_open: Mapped[float | None] = mapped_column(Float)
    event: Mapped[int | None] = mapped_column(Integer)                # 1 = 폐업
    closed_within_24m: Mapped[int | None] = mapped_column(Integer)    # NULL = open and younger than 24m
    area_m2: Mapped[float | None] = mapped_column(Float)
    area_pyeong: Mapped[float | None] = mapped_column(Float)
    road_addr: Mapped[str | None] = mapped_column(Text)
    x_5181: Mapped[float | None] = mapped_column(Float)
    y_5181: Mapped[float | None] = mapped_column(Float)
    coord_source: Mapped[str | None] = mapped_column(String(24))


class HeroAttribute(Base):
    """Hero-store values. low/base/high are text (some are categories); *_num holds the numeric form."""
    __tablename__ = "hero_attribute"
    industry_id: Mapped[str] = mapped_column(ForeignKey("industry.industry_id"), primary_key=True)
    criterion_id: Mapped[str] = mapped_column(ForeignKey("criterion.criterion_id"), primary_key=True)
    low: Mapped[str | None] = mapped_column(String(60))
    base: Mapped[str | None] = mapped_column(String(60))
    high: Mapped[str | None] = mapped_column(String(60))
    low_num: Mapped[float | None] = mapped_column(Float)
    base_num: Mapped[float | None] = mapped_column(Float)
    high_num: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    method: Mapped[str | None] = mapped_column(String(20))   # public | guesstimate | interview_later | derived
    source_id: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[str | None] = mapped_column(String(4))
    reasoning_chain: Mapped[str | None] = mapped_column(Text)
    filled_by: Mapped[str | None] = mapped_column(String(40))    # AI | formula | <member>
    reviewed_by: Mapped[str | None] = mapped_column(String(40))  # NULL until a named human reviews it


class DocChunk(Base):
    __tablename__ = "doc_chunk"
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)   # sha256(doc_id + index + text)[:32]
    doc_id: Mapped[str] = mapped_column(String(200))
    source_id: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embed_model: Mapped[str | None] = mapped_column(String(80))
    embedding = mapped_column(Embedding)


class Scenario(Base):
    __tablename__ = "scenario"
    scenario_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    industry_id: Mapped[str | None] = mapped_column(ForeignKey("industry.industry_id"))
    name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict | None]            # e.g. the hero base P&L (_pnl_base) and _meta


class Shock(Base):
    __tablename__ = "shock"
    shock_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    industry_id: Mapped[str | None] = mapped_column(ForeignKey("industry.industry_id"))
    driver: Mapped[str | None] = mapped_column(String(40))
    name_ko: Mapped[str | None] = mapped_column(String(200))
    parameter: Mapped[str | None] = mapped_column(String(60))
    delta_type: Mapped[str | None] = mapped_column(String(20))
    delta_low: Mapped[float | None] = mapped_column(Float)
    delta_base: Mapped[float | None] = mapped_column(Float)
    delta_high: Mapped[float | None] = mapped_column(Float)
    mechanism: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[str | None] = mapped_column(String(4))
    spec: Mapped[dict | None]              # the full row as loaded


class SimRun(Base):
    __tablename__ = "sim_run"
    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("scenario.scenario_id"))
    shock_id: Mapped[str | None] = mapped_column(ForeignKey("shock.shock_id"))
    runs: Mapped[int | None] = mapped_column(Integer)
    seed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20))
    owner_action: Mapped[dict | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meta: Mapped[dict | None]


class SimKpi(Base):
    __tablename__ = "sim_kpi"
    run_id: Mapped[str] = mapped_column(ForeignKey("sim_run.run_id"), primary_key=True)
    variant: Mapped[str] = mapped_column(String(20), primary_key=True)   # base | shock | reaction
    kpi: Mapped[str] = mapped_column(String(60), primary_key=True)
    p10: Mapped[float | None] = mapped_column(Float)
    p50: Mapped[float | None] = mapped_column(Float)
    p90: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))


class SimEvent(Base):
    __tablename__ = "sim_event"
    __table_args__ = (UniqueConstraint("run_id", "variant", "seq"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("sim_run.run_id"))
    variant: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    t_min: Mapped[float | None] = mapped_column(Float)        # minutes since opening
    event_type: Mapped[str | None] = mapped_column(String(20))  # arrive | queue | seat | order | leave | balk
    party_id: Mapped[int | None] = mapped_column(Integer)
    table_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict | None]


class GameSession(Base):
    """A v2 season (docs/GAME-V2-SPEC.md §11). The API keeps live sessions in memory and writes every change
    here, so a season survives an API restart."""
    __tablename__ = "game_session"
    season_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mode: Mapped[str] = mapped_column(String(12))            # guided | free | sandbox
    seed: Mapped[int] = mapped_column(Integer)
    engine: Mapped[str | None] = mapped_column(String(40))   # sim.season | stub
    state: Mapped[dict | None]                               # SeasonState after the last played month
    months: Mapped[list | None]                              # MonthResult per played month (persona text included)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
