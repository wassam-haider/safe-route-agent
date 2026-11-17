import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import reset_session, run_turn
from app.config import BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx INFO logs print full URLs, including API keys

app = FastAPI(title="SafeRoute Agent")


class ChatIn(BaseModel):
    session_id: str
    message: str


class ResetIn(BaseModel):
    session_id: str


@app.post("/api/chat")
def chat(payload: ChatIn):
    try:
        return run_turn(payload.session_id, payload.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reset")
def reset(payload: ResetIn):
    reset_session(payload.session_id)
    return {"ok": True}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")