from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
import aiofiles
import os
from uuid import uuid4
from pydantic import BaseModel

router = APIRouter()

BASE_STORAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage"))
RAW_DIR = os.path.join(BASE_STORAGE, "raw_uploads")
os.makedirs(RAW_DIR, exist_ok=True)

@router.post("/datasets/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    # basic validation
    filename = str(file.filename)
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="only csv and xlsx allowed")

    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}__{os.path.basename(filename)}" 
    dest = os.path.join(RAW_DIR, safe_name)

    try:
        async with aiofiles.open(dest, "wb") as out:
            content = await file.read()
            await out.write(content)
    finally:
        await file.close()

    payload = {
        "dataset_id": dataset_id,
        "filename": filename,
        "stored_path": dest,
        "status": "uploaded",
    }
    return JSONResponse(status_code=201, content=payload)


"""
requestJson(
"/api/v1/analysis/jobs"
, { method: "POST", body: JSON.stringify(...)
, headers: {...} })
"""

#pydantic validator to ensure payload is good
class AnalysisJobRequest(BaseModel):
    dataset_id: str
    user_prompt: str

# route endpoint to handle queries from users - gives 422 automatically if bad input
@router.post("/dataset/jobs")
async def respond_job(payload: AnalysisJobRequest) -> dict:
    # validation of payload and request handler
    dataset_id = payload.dataset_id.strip()
    user_prompt = payload.user_prompt.strip()
    
    if not dataset_id or not user_prompt:
        HTTPException(status_code=400, detail="dataset_id and user_prompt required")

    # Process, the data with a function

    return {"status": "accepted", "dataset_id": dataset_id}

