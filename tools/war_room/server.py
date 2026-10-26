"""Servidor FastAPI do Squad War Room.

Ambiente de Ritos com Voz Neural Gratuita (edge-tts) + Chat Multi-Agente
Conectado ao Obsidian Vault em tempo real.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env da raiz do monorepo
PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
if PROJECT_ENV.exists():
    load_dotenv(dotenv_path=PROJECT_ENV, override=True)

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat_engine import ChatEngine
from obsidian_manager import ObsidianManager
from tts_service import TTSService, get_tts_status, synthesize_speech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("war_room_server")

app = FastAPI(
    title="Squad War Room • Tech Jobs Radar",
    description="Ambiente Apartado de Ritos com Voz Neural Gratuita + Chat Multi-Agente",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretórios
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_DIR = BASE_DIR / "benchmark_audio"
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

# Serviços
obsidian_mgr = ObsidianManager()
tts_service = TTSService()
chat_engine = ChatEngine(obsidian_mgr)


# Schemas Pydantic
class ChatRequest(BaseModel):
    message: str
    agent: str = "auto"
    rite: str = "general"
    history: Optional[List[Dict[str, str]]] = None


class BoardUpdateRequest(BaseModel):
    ticket: str
    status: str


class BoardLogRequest(BaseModel):
    title: str
    details: str
    agent: str = "@SM"


class TTSRequest(BaseModel):
    text: str
    agent: str = "sm"


@app.api_route("/", methods=["GET", "HEAD"])
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Squad War Room backend ativo. Crie o arquivo static/index.html"}


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Retorna o estado completo da squad, tarefas e conexão."""
    tasks = obsidian_mgr.parse_tasks()
    agents = chat_engine.get_agents_info()
    return {
        "status": "online",
        "is_gemini_online": chat_engine.is_online(),
        "tts": get_tts_status(),
        "agents": agents,
        "tasks": tasks,
        "sprint_raw": obsidian_mgr.read_sprint_ativa_raw(),
        "logs_raw": obsidian_mgr.read_logs_raw(),
    }


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest) -> Dict[str, Any]:
    """Processa a mensagem com o agente alvo ou auto-detectado."""
    result = await chat_engine.process_turn(
        user_message=payload.message,
        target_agent=payload.agent,
        rite=payload.rite,
        history=payload.history,
    )
    return result


@app.get("/api/tts")
async def tts_get(
    text: str = Query(..., description="Texto a ser falado"),
    agent: str = Query("sm", description="Agente (sm, tl, qa, po)"),
):
    """Sintetiza áudio via Gemini TTS (com fallback gracioso para edge-tts) e retorna como streaming de áudio MP3."""
    try:
        audio_path = await synthesize_speech(text=text, agent=agent)
        return Response(content=audio_path.read_bytes(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Erro ao sintetizar áudio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts")
async def tts_post(payload: TTSRequest):
    """Endpoint POST para síntese de áudio."""
    try:
        audio_path = await synthesize_speech(text=payload.text, agent=payload.agent)
        return Response(content=audio_path.read_bytes(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Erro ao sintetizar áudio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/board/update")
async def update_board(payload: BoardUpdateRequest):
    """Atualiza o status de uma task no arquivo Sprint Ativa.md."""
    success = obsidian_mgr.update_task_status(payload.ticket, payload.status)
    if not success:
        raise HTTPException(status_code=400, detail=f"Tarefa {payload.ticket} não encontrada no quadro.")

    obsidian_mgr.append_event_log(
        title=f"Quadro Atualizado: {payload.ticket} -> {payload.status}",
        details=f"Status da tarefa {payload.ticket} modificado para `{payload.status}` via War Room.",
        agent="@SM",
    )

    return {
        "success": True,
        "ticket": payload.ticket,
        "new_status": payload.status,
        "tasks": obsidian_mgr.parse_tasks(),
    }


@app.post("/api/board/log")
async def append_log(payload: BoardLogRequest):
    """Adiciona um registro ao Log de Ritos & Sabatinas.md."""
    success = obsidian_mgr.append_event_log(
        title=payload.title,
        details=payload.details,
        agent=payload.agent,
    )
    return {"success": success}


# Monta pastas estáticas
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/benchmark_audio", StaticFiles(directory=str(BENCHMARK_DIR)), name="benchmark_audio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8765, reload=True)
