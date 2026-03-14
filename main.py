# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.db import create_tables
from routers import session, bot, trades

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield

app = FastAPI(title="AutoTrader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router, prefix="/session", tags=["Session"])
app.include_router(bot.router,     prefix="/bot",     tags=["Bot"])
app.include_router(trades.router,  prefix="/trades",  tags=["Trades"])

@app.get("/")
def root():
    return {"status": "ok"}
