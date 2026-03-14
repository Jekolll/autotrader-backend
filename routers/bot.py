# routers/bot.py
from fastapi import APIRouter, HTTPException, Header
from services import bot_runner

router = APIRouter()

def _token(authorization: str = Header(...)) -> str:
    return authorization.replace("Bearer ", "")

@router.post("/start")
def start(authorization: str = Header(...)):
    res = bot_runner.start(_token(authorization))
    if not res["ok"]: raise HTTPException(400, res["msg"])
    return res

@router.post("/stop")
def stop(authorization: str = Header(...)):
    return bot_runner.stop(_token(authorization))

@router.get("/status")
def get_status(authorization: str = Header(...)):
    return bot_runner.status(_token(authorization))
