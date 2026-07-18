from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from models import DiagnoseRequest
from orchestrator import DiagnosisOrchestrator, format_sse

app = FastAPI(title="TriageSwarm Backend", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if not cors_origins:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = DiagnosisOrchestrator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/diagnose")
async def diagnose(request: DiagnoseRequest):
    async def event_stream():
        async for event in orchestrator.stream(request):
            yield format_sse(event["event"], event["data"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/diagnose.json")
def diagnose_json(request: DiagnoseRequest):
    return JSONResponse(orchestrator.diagnose(request).model_dump())
