import os
import asyncio
import logging
import psycopg2
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("haruhan")

app = FastAPI(title="Haruhan Backend", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ----------------------------------------------------
# 1. Supabase 절면증 방지 (Ping) 로직 & 스케줄러
# ----------------------------------------------------
def keep_supabase_alive():
    """Supabase DB에 SELECT 1 쿼리를 날려 7일 비활성화 정지를 방지"""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL이 설정되지 않았습니다.")
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        conn.close()
        logger.info("🟢 [Supabase Ping] DB가 성공적으로 살아있음을 확인했습니다.")
    except Exception as e:
        logger.error(f"🔴 [Supabase Ping] DB 통신 실패: {e}")

# 백그라운드 스케줄러 세팅 (매일 새벽 3시 실행)
scheduler = BackgroundScheduler()
scheduler.add_job(keep_supabase_alive, 'cron', hour=3, minute=0)

@app.on_event("startup")
def startup_event():
    scheduler.start()
    # 서버 기동 시 즉시 한번 DB 찌르기
    keep_supabase_alive()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

# ----------------------------------------------------
# 2. DTO (요청/응답 모델)
# ----------------------------------------------------
class ChatRequest(BaseModel):
    prompt: str
    model: str = "qwen2.5:3b"

# ----------------------------------------------------
# 3. 라우트 (API Endpoints)
# ----------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "haruhan-backend"}

@app.post("/api/chat")
async def chat_with_ollama(request: ChatRequest):
    """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하는 엔드포인트"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": request.model,
                    "prompt": request.prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return {"result": data.get("response", "")}
        except httpx.HTTPError as e:
            logger.error(f"Ollama API 호출 에러: {e}")
            raise HTTPException(status_code=500, detail="Ollama 엔진 응답 실패")