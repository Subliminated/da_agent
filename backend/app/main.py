
# Python web framwork for building APIs quickly and reliably 
from fastapi import FastAPI, Request 

# Adds cross-origin Resource sharing (CORS), handles preflight requests.
# CORS allows browser based apps to call API by adding necessary headers and preflight requests 
# Without CORS, any upload routes from front end will be blocked 
from fastapi.middleware.cors import CORSMiddleware 
from uuid import uuid4

app = FastAPI(title="data-analyst-agent-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
from .api.v1.routes import respond as respond_router
app.include_router(upload_router.router, prefix="/api/v1")
app.include_router(respond_router.router, prefix="/api/v1")
