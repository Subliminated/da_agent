from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status
from fastapi.responses import JSONResponse
import asyncio
from typing import Any
from pydantic import BaseModel
import os
import glob

from ....core.config import RAW_UPLOADS_DIR, STORAGE_ROOT, UPLOAD_HASH_DIR, UPLOAD_HASH_INDEX_FILE

router = APIRouter()
RAW_DIR = str(RAW_UPLOADS_DIR)

def _validate_dataset_id(dataset_id: str) -> str | None:
    matches = glob.glob(os.path.join(RAW_DIR, f"{dataset_id}*"))
    # Handle duplicate ID's 
    return matches[0] if (len(matches) > 0) else None

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

