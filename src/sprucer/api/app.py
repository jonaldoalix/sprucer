from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sprucer.adapters.auth import AuthAdapter, AuthContext, create_auth
from sprucer.adapters.llm import OpenAICompatLlm
from sprucer.adapters.storage import create_storage
from sprucer.service import CareerService
from sprucer.settings import Settings, get_settings


class LoginBody(BaseModel):
    password: str | None = None
    api_key: str | None = None


class TruthPatchBody(BaseModel):
    op: str
    section: str
    item: dict[str, Any] | str | None = None
    item_id: str | None = None
    index: int | None = None
    value: Any = None
    confirm: bool = False


class AppUpsertBody(BaseModel):
    id: str | None = None
    application_id: str | None = None
    company: str | None = None
    title: str | None = None
    location: str | None = None
    url: str | None = None
    status: str | None = None
    notes: str | None = None


class ConfirmBody(BaseModel):
    confirm: bool = False


class IngestBody(BaseModel):
    source_type: str = Field(description="paste|url|upload")
    text: str | None = None
    url: str | None = None
    filename: str | None = None
    content_base64: str | None = None
    application_id: str | None = None


class GenerateBody(BaseModel):
    application_id: str
    types: list[str] | None = None
    custom_type: str | None = None


class ApproveBody(BaseModel):
    application_id: str
    generation_id: str
    confirm: bool = False


def build_app(
    *,
    settings: Settings | None = None,
    service: CareerService | None = None,
    auth: AuthAdapter | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if service is None:
        store = create_storage(settings.database_url)
        llm = OpenAICompatLlm(
            base_url=settings.llm_url,
            api_key=settings.llm_api_key,
            default_model=settings.llm_model,
        )
        service = CareerService(store, llm)
    if auth is None:
        auth = create_auth(
            mode=settings.auth_mode,
            dev_password=settings.dev_password,
            session_secret=settings.session_secret,
            api_keys=settings.api_key_set(),
            oidc_issuer=settings.oidc_issuer,
            oidc_client_id=settings.oidc_client_id,
            oidc_client_secret=settings.oidc_client_secret,
        )

    app = FastAPI(title="Sprucer", version="0.1.0", docs_url="/docs", redoc_url="/redoc")
    app.state.settings = settings
    app.state.service = service
    app.state.auth = auth

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list() or ["http://127.0.0.1:3737"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_auth(request: Request) -> AuthContext:
        return app.state.auth.authenticate(request)

    def svc() -> CareerService:
        return app.state.service

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "sprucer", "auth_mode": app.state.auth.mode}

    @app.post("/v1/auth/login")
    def login(payload: LoginBody, response: Response) -> dict[str, Any]:
        ctx = app.state.auth.login(response, password=payload.password, api_key=payload.api_key)
        return {"ok": True, "subject": ctx.subject, "mode": ctx.mode}

    @app.post("/v1/auth/logout")
    def logout(response: Response) -> dict[str, Any]:
        app.state.auth.logout(response)
        return {"ok": True}

    @app.get("/v1/auth/whoami")
    def whoami(ctx: AuthContext = Depends(require_auth)) -> dict[str, Any]:
        return {"ok": True, "subject": ctx.subject, "mode": ctx.mode}

    @app.get("/v1/truth")
    def truth_get(_: AuthContext = Depends(require_auth), service: CareerService = Depends(svc)):
        return service.truth_get()

    @app.patch("/v1/truth")
    def truth_patch(
        payload: TruthPatchBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            item = payload.item if isinstance(payload.item, dict) else (
                {"text": payload.item} if isinstance(payload.item, str) else None
            )
            return service.truth_patch(
                op=payload.op,
                section=payload.section,
                item=item,
                item_id=payload.item_id,
                index=payload.index,
                value=payload.value,
                confirm=payload.confirm,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/applications")
    def applications_list(_: AuthContext = Depends(require_auth), service: CareerService = Depends(svc)):
        return service.applications_list()

    @app.get("/v1/applications/{application_id}")
    def applications_get(
        application_id: str,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return service.applications_get(application_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/applications")
    def applications_upsert(
        payload: AppUpsertBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return service.applications_upsert(payload.model_dump(exclude_none=True))
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/applications/{application_id}/delete")
    def applications_delete(
        application_id: str,
        payload: ConfirmBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return service.applications_delete(application_id, confirm=payload.confirm)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/jd/ingest")
    async def jd_ingest(
        payload: IngestBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return await service.jd_ingest(
                source_type=payload.source_type,
                text=payload.text,
                url=payload.url,
                filename=payload.filename,
                content_base64=payload.content_base64,
                application_id=payload.application_id,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/generate")
    async def generate(
        payload: GenerateBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return await service.generate(
                application_id=payload.application_id,
                types=payload.types,
                custom_type=payload.custom_type,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/generations/approve")
    def generation_approve(
        payload: ApproveBody,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return service.generation_approve(
                application_id=payload.application_id,
                generation_id=payload.generation_id,
                confirm=payload.confirm,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/applications/{application_id}/generations/{generation_id}")
    def generation_get(
        application_id: str,
        generation_id: str,
        _: AuthContext = Depends(require_auth),
        service: CareerService = Depends(svc),
    ):
        try:
            return service.generation_get(application_id=application_id, generation_id=generation_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = build_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "sprucer.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
