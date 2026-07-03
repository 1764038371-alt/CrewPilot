from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.planning.router import router as planning_router
from app.modules.proposals.router import proposal_router, schedule_version_router
from app.modules.schedule.router import router as schedule_router
from app.modules.schedule_editor.explanations import router as explanation_router
from app.modules.setup.router import router as setup_router
from app.modules.stores.router import router as stores_router
from app.modules.workspaces.router import router as workspaces_router

app = FastAPI(title="CrewPilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(planning_router, prefix=api_prefix)
app.include_router(schedule_version_router, prefix=api_prefix)
app.include_router(proposal_router, prefix=api_prefix)
app.include_router(schedule_router, prefix=api_prefix)
app.include_router(explanation_router, prefix=api_prefix)
app.include_router(setup_router, prefix=api_prefix)
app.include_router(stores_router, prefix=api_prefix)
app.include_router(workspaces_router, prefix=api_prefix)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
