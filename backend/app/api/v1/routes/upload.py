from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status
from fastapi.responses import JSONResponse
import aiofiles
import os
from uuid import uuid4
from pydantic import BaseModel
import glob
import hashlib
import json
import threading
import asyncio
import time

router = APIRouter()

BASE_STORAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage"))
RAW_DIR = os.path.join(BASE_STORAGE, "raw_uploads")
HASH_DIR = os.path.join(BASE_STORAGE, "upload_hash")
HASH_FILE = os.path.join(HASH_DIR,"index.json")

# Create hashing locks to avoid data correction and call blocking for asynchronous calls 
_index_lock = threading.Lock()

CHUNK = 8192
os.makedirs(HASH_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

##### helper for hash
def _generate_data_hash(data_read: bytes) -> str:
    "Create unique hash for file data using hash function"
    hash_str = hashlib.sha256(data_read).hexdigest()
    return hash_str

def _load_index() -> dict:
    try:
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def _save_index(index: dict) -> None:
    tmp = HASH_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HASH_FILE)  # atomic on POSIX

def get_by_hash(file_hash: str) -> str | None:
    with _index_lock:
        index = _load_index()
        return index.get(file_hash, None)

def insert_hash(file_hash: str, meta: str) -> None:
    """
    Store a file hash and its metadata in the index.
    Args:
        file_hash (str): The hash identifier of the file.
        meta (dict): Metadata associated with the file hash. (dataset ID)
    """
    with _index_lock:
        index = _load_index()
        index[file_hash] = meta
        _save_index(index)

@router.post("/datasets/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    """
    Upload a dataset file to the server.
    This endpoint accepts CSV or XLSX files and stores them in the raw data directory.
    The uploaded file is renamed with a UUID prefix to ensure uniqueness.
    Args:
        request (Request): The HTTP request object.
        file (UploadFile): The file to be uploaded. Must be a CSV or XLSX file.
    Returns:
        JSONResponse: A JSON response with status code 201 containing:
            - dataset_id (str): Unique identifier for the uploaded dataset.
            - filename (str): Original name of the uploaded file.
            - stored_path (str): File system path where the dataset was stored.
            - status (str): Upload status ("uploaded").
    Raises:
        HTTPException: If the file extension is not CSV or XLSX (status code 400).
    Note:
        - Files are renamed with a UUID prefix to prevent naming conflicts.
        - The file is closed automatically after upload completion.
    """

    # basic validation
    filename = str(file.filename)
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="only csv and xlsx allowed")

    # Stream upload to a temp file while hashing to avoid high memory usage
    temp_name = f"tmp_{uuid4().hex}"
    temp_dest = os.path.join(RAW_DIR, temp_name)
    hasher = hashlib.sha256()

    try:
        async with aiofiles.open(temp_dest, "wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                hasher.update(chunk)
                await out.write(chunk)
    finally:
        await file.close()

    file_hash = hasher.hexdigest()

    # Run index lookup/updates in threadpool to avoid blocking the event loop
    loop = asyncio.get_running_loop()
    existing = await loop.run_in_executor(None, get_by_hash, file_hash)
    if existing:
        # existing should be metadata dict; cleanup temp and return duplicate info
        try:
            os.remove(temp_dest)
        except OSError:
            pass
        payload = {
            "dataset_id": existing.get("dataset_id") if isinstance(existing, dict) else existing,
            "filename": existing.get("filename") if isinstance(existing, dict) else filename,
            "stored_path": existing.get("stored_path") if isinstance(existing, dict) else None,
            "status": "duplicate",
        }
        return JSONResponse(status_code=200, content=payload)

    # Not found: commit file under a safe name and insert index entry
    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}__{os.path.basename(filename)}"
    final_dest = os.path.join(RAW_DIR, safe_name)

    # Atomic move
    os.replace(temp_dest, final_dest)

    meta = {
        "dataset_id": dataset_id,
        "stored_path": final_dest,
        "filename": filename,
        "created_at": time.time(),
    }

    await loop.run_in_executor(None, insert_hash, file_hash, meta)

    payload = {
        "dataset_id": dataset_id,
        "filename": filename,
        "stored_path": final_dest,
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

def structured_error(status_code: int, code: str, message: str, details: dict | None = None):
    payload = {"error": {"code": code, "message": message, "details": None}}
    if details is not None:
        payload["error"]["details"] = details
    raise HTTPException(status_code=status_code, detail=payload)

# route endpoint to handle queries from users - gives 422 automatically if bad input
@router.post("/dataset/jobs")
async def respond_job(payload: AnalysisJobRequest) -> dict:
    """
    Process an analysis job request and queue it for asynchronous processing.
    This function validates the incoming analysis job request payload, ensures
    required fields are present, and initiates the data analysis workflow for
    the specified dataset.
    Args:
        payload (AnalysisJobRequest): The analysis job request containing:
            - dataset_id (str): The unique identifier of the dataset to analyze
            - user_prompt (str): The user's natural language query or instruction
              for data analysis
    Returns:
        dict: A response dictionary containing:
            - status (str): Job status indicator, typically "accepted"
            - dataset_id (str): The dataset ID that was submitted for processing
    Raises:
        HTTPException: If dataset_id or user_prompt is missing or empty
            (status_code=400, detail="dataset_id and user_prompt required")
    Example:
        >>> payload = AnalysisJobRequest(
        ...     dataset_id="ds_12345",
        ...     user_prompt="Show me the sales trends"
        ... )
        >>> response = await respond_job(payload)
        >>> print(response)
        {'status': 'accepted', 'dataset_id': 'ds_12345'}
    """
    
    # validation of payload and request handler
    dataset_id = payload.dataset_id.strip()
    user_prompt = payload.user_prompt.strip()

    # If validatioon succeeds, find the id
    if not dataset_id or not user_prompt:
        #raise HTTPException(status_code=400, detail="dataset_id and user_prompt required")
        structured_error(status.HTTP_400_BAD_REQUEST, "MISSING_FIELDS", "dataset_id and user_prompt required")

    stored_path = _validate_dataset_id(dataset_id)
    # Process, the data with a function
    if not stored_path:
        #raise HTTPException(status_code=404, detail="dataset_id not found")
        structured_error(status.HTTP_404_NOT_FOUND, "DATASET_NOT_FOUND", "dataset_id not found")

    return {"status": "accepted", "dataset_id": dataset_id}

def _validate_dataset_id(dataset_id: str) -> str | None:
    matches = glob.glob(os.path.join(RAW_DIR, f"{dataset_id}*"))
    # Handle duplicate ID's 
    return matches[0] if (len(matches) > 0) else None


