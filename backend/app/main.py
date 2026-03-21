
# Python web framwork for building APIs quickly and reliably 
from fastapi import FastAPI, Request 

# Adds cross-origin Resource sharing (CORS), handles preflight requests.
# CORS allows browser based apps to call API by adding necessary headers and preflight requests 
# Without CORS, any upload routes from front end will be blocked 
from fastapi.middleware.cors import CORSMiddleware 
from uuid import uuid4
import os

app = FastAPI(title="data-analyst-agent-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ensure storage dirs exist
BASE = os.path.join(os.path.dirname(__file__), "..", "..", "storage")
RAW = os.path.abspath(os.path.join(BASE, "raw_uploads"))
PARSED = os.path.abspath(os.path.join(BASE, "parsed_datasets"))
ARTIFACTS = os.path.abspath(os.path.join(BASE, "job_artifacts"))
os.makedirs(RAW, exist_ok=True)
os.makedirs(PARSED, exist_ok=True)
#os.makedirs(ARTIFACTS, exist_ok=True)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

# include router lazily to avoid import cycles
from .api.v1.routes import upload as upload_router
app.include_router(upload_router.router, prefix="/api/v1")
