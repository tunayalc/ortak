from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .config import get_settings
from .db import get_conn, init_db
from .schemas import (
    CandidateSearchRequest,
    ExperimentRequest,
    ExperimentResponse,
    LocationParseRequest,
    ParsedLocation,
    PlaceCandidate,
    PreferenceInterpretRequest,
    PreferenceSuggestion,
    RecommendationRequest,
    RecommendationResponse,
    RouteMatrixRequest,
    RouteMetric,
    Scenario,
    ScenarioCreate,
)
from .services.experiments import run_experiment
from .services.google_maps import build_route_matrix, search_candidates
from .services.google_transport import capture_google_calls
from .services.google_usage import GoogleUsageBlocked, ensure_capacity, usage_status
from .services.location_parser import parse_location_inputs
from .services.preference_interpreter import PreferenceServiceError, interpret_preferences, llm_status
from .services.scenario import create_scenario, get_scenario
from .services.scoring import recommend
from .services import session_store
from .services.public_safety import PublicSafetyMiddleware


router = APIRouter()
_model_lock = asyncio.Lock()
_google_work_lock = asyncio.Lock()


async def google_call_metadata(request, call_next):
    with capture_google_calls() as events:
        response = await call_next(request)
    response.headers["X-ORTAK-Google-Calls"] = str(len(events))
    response.headers["X-ORTAK-Google-Retries"] = str(sum(event["attempt"] > 1 for event in events))
    response.headers["X-ORTAK-Google-Elapsed-Ms"] = str(round(sum(event["elapsed_ms"] for event in events), 2))
    return response


@asynccontextmanager
async def lifespan(app):
    init_db()
    async def cleanup():
        while True:
            session_store.cleanup_expired()
            await asyncio.sleep(30)
    task = asyncio.create_task(cleanup())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    usage = usage_status()
    return {
        "status": "ok",
        "google_configured": settings.has_google_key,
        "google_status": "configured_not_verified" if settings.has_google_key else "unconfigured",
        "google_services": ["Places API (New)", "Routes API", "Geocoding API"],
        "google_usage": {key: usage[key] for key in ("calls_enabled", "available", "budget_enforced", "budget_limit_tl", "max_attempts_per_request")} if settings.production else usage,
        **(await llm_status()),
        **({} if settings.production else {"osrm_base_url": settings.osrm_base_url}),
    }


@router.get("/runtime-config")
def runtime_config(request: Request):
    settings = get_settings()
    usage = usage_status()
    return {
        "production": settings.production,
        "csrf_token": request.session.get("csrf", "") if settings.production else "",
        "max_participants": settings.public_max_participants if settings.production else 12,
        "max_candidates": settings.public_max_candidates if settings.production else 12,
        "max_k": settings.public_max_k if settings.production else 20,
        "session_ttl_seconds": session_store.SESSION_TTL_SECONDS,
        "google_available": settings.has_google_key and usage.get("available", False),
        "google_remaining_requests": usage["remaining_today"],
        "google_service_remaining": usage.get("service_remaining", {}),
        "google_unavailable_reason": usage.get("unavailable_reason", ""),
    }


@router.get("/readyz")
def readyz():
    with get_conn() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@router.post("/locations/parse", response_model=list[ParsedLocation])
async def post_locations_parse(payload: LocationParseRequest) -> list[ParsedLocation]:
    if get_settings().production and len(payload.items) > get_settings().public_max_participants:
        raise HTTPException(400, "En fazla 8 kişi konumu girilebilir.")
    return await parse_location_inputs(payload.items)


@router.post("/preferences/interpret", response_model=PreferenceSuggestion)
async def post_preferences_interpret(payload: PreferenceInterpretRequest) -> PreferenceSuggestion:
    if get_settings().production and len(payload.participants) > get_settings().public_max_participants:
        raise HTTPException(400, "En fazla 8 kişi kullanılabilir.")
    if _model_lock.locked():
        raise HTTPException(429, "Model şu anda başka bir isteği işliyor. Manuel ayarları kullanabilir veya kısa süre sonra yeniden deneyebilirsiniz.")
    try:
        async with _model_lock:
            return await interpret_preferences(payload)
    except PreferenceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/scenarios", response_model=Scenario)
async def post_scenario(payload: ScenarioCreate) -> Scenario:
    settings = get_settings()
    if settings.production:
        if not settings.has_google_key:
            raise HTTPException(503, "Google bağlantısı hazır değil. Yeni ücretli işlem başlatılmadı.")
        size = len(payload.participant_locations or []) if payload.input_mode == "link" else payload.group_size
        if size > settings.public_max_participants or payload.users or payload.synthetic_fixture:
            raise HTTPException(400, "En fazla 8 kişi kullanılabilir; doğrudan test verisi yalnızca yerel geliştirmede kabul edilir.")
        if payload.category not in {"cafe", "restaurant", "park", "library", "museum"}:
            raise HTTPException(400, "Desteklenen bir mekân türü seçin.")
        try:
            session_store.ensure_capacity()
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from exc
        ensure_capacity(size * settings.public_max_candidates + 2)
    try:
        if _google_work_lock.locked():
            raise HTTPException(429, "Başka bir konum işlemi sürüyor. Kısa süre sonra yeniden deneyin.")
        async with _google_work_lock:
            return await create_scenario(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GoogleUsageBlocked:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Konum işlemi tamamlanamadı. Daha sonra yeniden deneyin.") from exc


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
def get_scenario_endpoint(scenario_id: str) -> Scenario:
    try:
        return get_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario_endpoint(scenario_id: str):
    if not session_store.delete_scenario(scenario_id):
        raise HTTPException(404, "Senaryo bulunamadı veya oturum süresi doldu.")


@router.post("/candidates/search", response_model=list[PlaceCandidate])
async def post_candidates(payload: CandidateSearchRequest) -> list[PlaceCandidate]:
    if get_settings().production and payload.max_results > get_settings().public_max_candidates:
        raise HTTPException(400, "Bu beta sürümde en fazla 3 mekân aranabilir.")
    try:
        if _google_work_lock.locked():
            raise HTTPException(429, "Mekân ve rota servisi meşgul. Kısa süre sonra yeniden deneyin.")
        async with _google_work_lock:
            return await search_candidates(payload.scenario_id, payload.max_results, payload.radius_m)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoogleUsageBlocked:
        raise
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Mekân araması tamamlanamadı. Daha sonra yeniden deneyin.") from exc


@router.post("/routes/matrix", response_model=list[RouteMetric])
async def post_routes(payload: RouteMatrixRequest) -> list[RouteMetric]:
    if get_settings().production and (payload.provider not in {"auto", "google"} or not get_settings().has_google_key):
        raise HTTPException(400, "Canlı sürümde yalnızca doğrulanmış Google rotaları kullanılır.")
    try:
        if _google_work_lock.locked():
            raise HTTPException(429, "Mekân ve rota servisi meşgul. Kısa süre sonra yeniden deneyin.")
        async with _google_work_lock:
            return await build_route_matrix(payload.scenario_id, payload.provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoogleUsageBlocked:
        raise
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Rota matrisi tamamlanamadı. Eksik rotalar gerçek başarı olarak gösterilmez.") from exc


@router.post("/recommendations", response_model=RecommendationResponse)
def post_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    if get_settings().production and payload.k > get_settings().public_max_k:
        raise HTTPException(400, "En fazla 3 öneri gösterilebilir.")
    try:
        return recommend(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/experiments/run", response_model=ExperimentResponse)
def post_experiment(payload: ExperimentRequest) -> ExperimentResponse:
    try:
        return run_experiment(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="ORTAK API", version="0.2.0", lifespan=lifespan,
                          docs_url=None if settings.production else "/docs",
                          redoc_url=None if settings.production else "/redoc")
    application.include_router(router)
    application.middleware("http")(google_call_metadata)
    application.add_middleware(CORSMiddleware, allow_origins=settings.origins,
                               allow_credentials=True, allow_methods=["GET", "POST", "DELETE"],
                               allow_headers=["Content-Type", "X-ORTAK-CSRF"])
    if settings.production:
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlparse(settings.public_base_url).hostname])
    application.add_middleware(PublicSafetyMiddleware, settings=settings)
    application.add_middleware(SessionMiddleware,
                               secret_key=settings.session_secret or "local-development-only-not-for-production",
                               session_cookie="ortak_session", max_age=session_store.SESSION_TTL_SECONDS,
                               same_site="lax", https_only=settings.production)

    @application.exception_handler(GoogleUsageBlocked)
    async def quota_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=429)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo a rejected body (coordinates, links or preference text).
        errors = [{"loc": list(error["loc"]), "msg": "Geçersiz veya izin verilen aralığın dışında bir değer."} for error in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    return application


app = create_app()
