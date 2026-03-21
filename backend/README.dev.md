Development notes

Run the FastAPI app locally (after installing requirements):

```bash
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Upload endpoint:
- POST /api/v1/datasets/upload (multipart form field `file`)

Storage locations are created automatically under `backend/storage/`.
