from fastapi import FastAPI

from src.app.api.v1.analyze import router as analyze_router
from src.app.api.v1.jobs import router as jobs_router
from src.app.api.v1.reports import router as reports_router

app = FastAPI(title="AI Content Analyzer")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(analyze_router)
app.include_router(jobs_router)
app.include_router(reports_router)