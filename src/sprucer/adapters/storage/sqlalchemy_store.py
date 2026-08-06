from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Base(DeclarativeBase):
    pass


class TruthRow(Base):
    __tablename__ = "truth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    company: Mapped[str] = mapped_column(String(300), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    source_type: Mapped[str] = mapped_column(String(40), default="paste")
    source_filename: Mapped[str] = mapped_column(String(400), default="")
    source_sha256: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    notes: Mapped[str] = mapped_column(Text, default="")
    jd_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    generations: Mapped[list[GenerationRow]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="GenerationRow.created_at",
    )


class GenerationRow(Base):
    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    types_json: Mapped[str] = mapped_column(Text, default="[]")
    emphasis_json: Mapped[str] = mapped_column(Text, default="[]")
    content: Mapped[str] = mapped_column(Text, default="")
    approval: Mapped[str] = mapped_column(String(40), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application: Mapped[ApplicationRow] = relationship(back_populates="generations")


EMPTY_TRUTH: dict[str, Any] = {
    "version": 1,
    "updatedAt": "",
    "profile": {},
    "headline": "",
    "voice": {"person": "first", "tone": "professional_not_bland", "punctuation": "keyboard_only"},
    "roleSpectrum": {},
    "education": {},
    "experience": [],
    "projects": [],
    "skills": {},
    "metrics": [],
    "neverClaim": [],
    "signatureStories": [],
    "blurbs": [],
    "resumePaths": {},
}


class SqlAlchemyStorage:
    """SQLite and Postgres via the same SQLAlchemy models."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            # Ensure parent dir exists for sqlite file URLs
            if database_url.startswith("sqlite:///./") or database_url.startswith("sqlite:////"):
                raw = database_url.removeprefix("sqlite:///")
                path = Path(raw)
                if not path.is_absolute():
                    path = Path.cwd() / path
                path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self._Session = sessionmaker(self.engine, expire_on_commit=False, class_=Session)

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        with self._Session() as session:
            row = session.scalar(select(TruthRow).limit(1))
            if row is None:
                doc = dict(EMPTY_TRUTH)
                doc["updatedAt"] = _now().isoformat()
                session.add(TruthRow(document=json.dumps(doc, ensure_ascii=True), updated_at=_now()))
                session.commit()

    def get_truth(self) -> dict[str, Any]:
        with self._Session() as session:
            row = session.scalar(select(TruthRow).limit(1))
            if row is None:
                return dict(EMPTY_TRUTH)
            return json.loads(row.document)

    def save_truth(self, truth: dict[str, Any]) -> dict[str, Any]:
        truth = dict(truth)
        truth["updatedAt"] = _now().isoformat()
        try:
            truth["version"] = int(truth.get("version") or 1) + 1
        except Exception:
            truth["version"] = 1
        with self._Session() as session:
            row = session.scalar(select(TruthRow).limit(1))
            payload = json.dumps(truth, ensure_ascii=True, indent=2)
            if row is None:
                session.add(TruthRow(document=payload, updated_at=_now()))
            else:
                row.document = payload
                row.updated_at = _now()
            session.commit()
        return truth

    def _app_dict(self, row: ApplicationRow, *, include_jd: bool = False) -> dict[str, Any]:
        gens = [
            {
                "id": g.id,
                "createdAt": _iso(g.created_at),
                "types": json.loads(g.types_json or "[]"),
                "emphasisPlan": json.loads(g.emphasis_json or "[]"),
                "approval": g.approval,
                "approvedAt": _iso(g.approved_at),
                "files": [],
            }
            for g in (row.generations or [])
        ]
        out: dict[str, Any] = {
            "id": row.id,
            "company": row.company,
            "title": row.title,
            "location": row.location,
            "url": row.url,
            "sourceType": row.source_type,
            "sourceFilename": row.source_filename,
            "sourceSha256": row.source_sha256,
            "status": row.status,
            "notes": row.notes,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "generations": gens,
        }
        if include_jd:
            out["jdText"] = row.jd_text
        return out

    def list_applications(self) -> list[dict[str, Any]]:
        with self._Session() as session:
            rows = session.scalars(select(ApplicationRow).order_by(ApplicationRow.updated_at.desc())).all()
            return [self._app_dict(r) for r in rows]

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        with self._Session() as session:
            row = session.get(ApplicationRow, application_id)
            if row is None:
                return None
            return self._app_dict(row, include_jd=True)

    def upsert_application(self, meta: dict[str, Any], *, jd_text: str | None = None) -> dict[str, Any]:
        app_id = str(meta["id"])
        with self._Session() as session:
            row = session.get(ApplicationRow, app_id)
            now = _now()
            if row is None:
                row = ApplicationRow(id=app_id, created_at=now)
                session.add(row)
            row.company = str(meta.get("company") or "")
            row.title = str(meta.get("title") or "")
            row.location = str(meta.get("location") or "")
            row.url = str(meta.get("url") or "")
            row.source_type = str(meta.get("sourceType") or meta.get("source_type") or "paste")
            row.source_filename = str(meta.get("sourceFilename") or "")
            row.source_sha256 = str(meta.get("sourceSha256") or "")
            row.status = str(meta.get("status") or "draft")
            row.notes = str(meta.get("notes") or "")
            if jd_text is not None:
                row.jd_text = jd_text
            row.updated_at = now
            session.commit()
            session.refresh(row)
            return self._app_dict(row, include_jd=True)

    def delete_application(self, application_id: str) -> None:
        with self._Session() as session:
            row = session.get(ApplicationRow, application_id)
            if row is None:
                raise KeyError(application_id)
            session.delete(row)
            session.commit()

    def get_jd(self, application_id: str) -> str:
        with self._Session() as session:
            row = session.get(ApplicationRow, application_id)
            if row is None:
                raise KeyError(application_id)
            return row.jd_text or ""

    def list_generations(self, application_id: str) -> list[dict[str, Any]]:
        app = self.get_application(application_id)
        if app is None:
            raise KeyError(application_id)
        return list(app.get("generations") or [])

    def get_generation(self, application_id: str, generation_id: str) -> dict[str, Any] | None:
        with self._Session() as session:
            row = session.get(GenerationRow, generation_id)
            if row is None or row.application_id != application_id:
                return None
            return {
                "id": row.id,
                "createdAt": _iso(row.created_at),
                "types": json.loads(row.types_json or "[]"),
                "emphasisPlan": json.loads(row.emphasis_json or "[]"),
                "approval": row.approval,
                "approvedAt": _iso(row.approved_at),
                "content": row.content,
                "files": [],
            }

    def save_generation(
        self,
        application_id: str,
        *,
        generation: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        with self._Session() as session:
            app = session.get(ApplicationRow, application_id)
            if app is None:
                raise KeyError(application_id)
            gen_id = str(generation["id"])
            row = GenerationRow(
                id=gen_id,
                application_id=application_id,
                types_json=json.dumps(generation.get("types") or [], ensure_ascii=True),
                emphasis_json=json.dumps(generation.get("emphasisPlan") or [], ensure_ascii=True),
                content=content,
                approval=str(generation.get("approval") or "draft"),
                created_at=_now(),
            )
            session.add(row)
            app.updated_at = _now()
            session.commit()
            return {
                "id": row.id,
                "createdAt": _iso(row.created_at),
                "types": generation.get("types") or [],
                "emphasisPlan": generation.get("emphasisPlan") or [],
                "approval": row.approval,
                "approvedAt": None,
                "files": [],
            }

    def approve_generation(self, application_id: str, generation_id: str) -> dict[str, Any]:
        with self._Session() as session:
            row = session.get(GenerationRow, generation_id)
            if row is None or row.application_id != application_id:
                raise KeyError(generation_id)
            row.approval = "approved"
            row.approved_at = _now()
            session.commit()
            return {
                "id": row.id,
                "createdAt": _iso(row.created_at),
                "types": json.loads(row.types_json or "[]"),
                "emphasisPlan": json.loads(row.emphasis_json or "[]"),
                "approval": row.approval,
                "approvedAt": _iso(row.approved_at),
                "files": [],
            }


def create_storage(database_url: str) -> SqlAlchemyStorage:
    store = SqlAlchemyStorage(database_url)
    store.ensure_schema()
    return store
