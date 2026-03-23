from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status
from fastapi.responses import JSONResponse
import aiofiles
import os
from uuid import uuid4
import hashlib
import asyncio
import time
from typing import Any

from ....core.config import RAW_UPLOADS_DIR, STORAGE_ROOT
from ....services.storage import get_by_hash, upsert_record

router = APIRouter()

RAW_DIR = str(RAW_UPLOADS_DIR)

CHUNK = 8192
os.makedirs(RAW_DIR, exist_ok=True)

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

    relative_stored_path = os.path.relpath(final_dest, str(STORAGE_ROOT))
    meta = {
        "dataset_id": dataset_id,
        "stored_path": relative_stored_path,
        "filename": filename,
        "created_at": time.time(),
    }

    await loop.run_in_executor(None, upsert_record, file_hash, meta)

    payload = {
        "dataset_id": dataset_id,
        "filename": filename,
        "stored_path": relative_stored_path,
        "status": "uploaded",
    }
    return JSONResponse(status_code=201, content=payload)

"""
requestJson(
"/api/v1/analysis/jobs"
, { method: "POST", body: JSON.stringify(...)
, headers: {...} })
"""