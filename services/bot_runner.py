# services/bot_runner.py
# Bot jalan di komputer user (local_bot.py)
# File ini hanya dummy agar tidak error di Railway

def start(token: str) -> dict:
    return {"ok": True, "msg": "Bot aktif — jalankan local_bot.py di komputer kamu"}

def stop(token: str) -> dict:
    return {"ok": True, "msg": "Bot dihentikan"}

def status(token: str) -> dict:
    return {"status": "stopped", "last_run": None, "error": None}
