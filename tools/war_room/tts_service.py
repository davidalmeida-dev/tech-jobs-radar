"""Serviço de Síntese de Voz Híbrida: Gemini 3.8 Flash-Lite TTS + Fallback Gracioso edge-tts.

Mapeia cada agente da Squad Tech Jobs Radar para uma voz do Gemini 3.8 TTS e seu fallback neural:
- @SM (Scrum Master): Gemini 3.8 Flash-Lite TTS (Kore) • Fallback: pt-BR-FranciscaNeural
- @TL (Tech Lead EY): Gemini 3.8 Flash-Lite TTS (Charon) • Fallback: pt-BR-AntonioNeural
- @QA (Data Quality): Gemini 3.8 Flash-Lite TTS (Fenrir) • Fallback: pt-BR-AntonioNeural
- @PO (Product Owner EY): Gemini 3.8 Flash-Lite TTS (Aoede) • Fallback: pt-BR-ThalitaMultilingualNeural
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
if PROJECT_ENV.exists():
    load_dotenv(dotenv_path=PROJECT_ENV, override=False)

import edge_tts

logger = logging.getLogger("tts_service")

# Circuit breaker flag: se Gemini API retornar 402 ou 429, evita chamadas redundantes
_gemini_quota_exhausted = False

# Mapeamento do Contrato Técnico Inviolável para Gemini 3.8 TTS e edge-tts
AGENT_VOICES: Dict[str, Dict[str, str]] = {
    "sm": {
        "gemini_model": "gemini-3.8-flash-lite-tts",
        "gemini_voice": "Kore",
        "edge_fallback": "pt-BR-FranciscaNeural",
    },
    "tl": {
        "gemini_model": "gemini-3.8-flash-lite-tts",
        "gemini_voice": "Charon",
        "edge_fallback": "pt-BR-AntonioNeural",
    },
    "qa": {
        "gemini_model": "gemini-3.8-flash-lite-tts",
        "gemini_voice": "Fenrir",
        "edge_fallback": "pt-BR-AntonioNeural",
    },
    "po": {
        "gemini_model": "gemini-3.8-flash-lite-tts",
        "gemini_voice": "Aoede",
        "edge_fallback": "pt-BR-ThalitaMultilingualNeural",
    },
}

# Configuração legada / edge-tts direta mantida para compatibilidade retroativa
AGENT_VOICE_CONFIG: Dict[str, Tuple[str, str, Optional[str]]] = {
    "sm": ("pt-BR-FranciscaNeural", "+0%", "+0Hz"),
    "tl": ("pt-BR-AntonioNeural", "+0%", "+0Hz"),
    "qa": ("pt-BR-AntonioNeural", "+0%", "+0Hz"),
    "po": ("pt-BR-ThalitaMultilingualNeural", "+0%", "+0Hz"),
}

CACHE_DIR = Path(__file__).parent / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clean_text_for_speech(text: str) -> str:
    """Sanitiza o texto removendo formatação Markdown, tabelas e links para fala fluida."""
    if not text:
        return ""

    # Remove blocos de código ```...```
    text = re.sub(r"```[\s\S]*?```", " [código detalhado no painel de notas] ", text)

    # Remove tags de alerta markdown (> [!NOTE], > [!IMPORTANT], etc.)
    text = re.sub(r">\s*\[![A-Z]+\][^\n]*", "", text)

    # Remove inline code `...`
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove links markdown [texto](url) mantendo só o texto
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove cabeçalhos markdown (#, ##, etc.)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)

    # Remove negrito e itálico (**texto**, *texto*, __texto__)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Remove bullet points markdown (* , - , + )
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Remove linhas de tabela (| coluna | coluna |)
    text = re.sub(r"\|[^\n]+\|", "", text)

    # Remove tags HTML
    text = re.sub(r"<[^>]+>", "", text)

    # Normalização Fonética de Estrangeirismos e Termos Técnicos para TTS pt-BR:
    # 1. 'time' (equipe) vs 'time' (tempo em inglês)
    text = re.sub(r"\b(olá|oi|fala|bom dia|boa tarde|nosso|nossa|o|ao|do|um|cada|todo|toda|grande)\s+time\b", r"\1 equipe", text, flags=re.IGNORECASE)
    text = re.sub(r"\btime\s+(técnico|ágil|de dados|da squad|de engenharia|inteiro)\b", r"equipe \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\btime\b", "equipe", text, flags=re.IGNORECASE)

    # 2. Termos Ágeis & Tech
    text = re.sub(r"\btimebox\b", "taimebox", text, flags=re.IGNORECASE)
    text = re.sub(r"\btimeboxes\b", "taimeboxes", text, flags=re.IGNORECASE)
    text = re.sub(r"\btimeboxing\b", "taimeboxing", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpipeline\b", "paipelaine", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpipelines\b", "paipelaines", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfeedback\b", "fidebéc", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdataops\b", "deitaóps", text, flags=re.IGNORECASE)
    text = re.sub(r"\blakehouse\b", "leikerause", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpyspark\b", "Pai Spark", text, flags=re.IGNORECASE)
    text = re.sub(r"\bduckdb\b", "Dâqui Dêbê", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfastapi\b", "Fásti Ápi", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwip\b", "uípi", text, flags=re.IGNORECASE)
    text = re.sub(r"\btjr-(\d+)\b", r"Tê Jota Erre \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdod\b", "Dê o Dê", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdor\b", "Dê o Erre", text, flags=re.IGNORECASE)
    text = re.sub(r"\bstar schema\b", "istár isquêma", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmerge into\b", "mêrge íntu", text, flags=re.IGNORECASE)

    # Remove múltiplos espaços em branco e quebras repetidas
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_tts_status() -> Dict[str, Any]:
    """Retorna o status atual dos motores de TTS e configuração de vozes dos agentes."""
    return {
        "primary_engine": "gemini-3.8-flash-lite-tts",
        "fallback_engine": "edge-tts",
        "gemini_tts_active": bool(os.getenv("GEMINI_API_KEY")),
        "voices": AGENT_VOICES,
    }


async def synthesize_speech(text: str, agent: str = "sm") -> Path:
    """Sintetiza áudio para o agente informado.
    
    Se GEMINI_API_KEY estiver configurada e não vazia, tenta sintetizar via SDK google-genai
    usando gemini-3.8-flash-lite-tts com a voz mapeada para o agente.
    Se a chave não estiver definida ou se houver qualquer falha/rate-limit,
    faz fallback gracioso transparente para edge-tts (rate='+0%', pitch='+0Hz').
    Grava os áudios gerados em audio_cache/ e retorna o Path para o arquivo.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Estou ouvindo. Pode prosseguir com o rito."

    agent_normalized = (agent or "sm").lower().replace("@", "").strip()
    agent_cfg = AGENT_VOICES.get(agent_normalized, AGENT_VOICES["sm"])

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    global _gemini_quota_exhausted

    # 1. Tentativa Primária: Gemini 3.8 Flash-Lite TTS com fallback para Gemini 3.8 Flash TTS
    if api_key and not _gemini_quota_exhausted:
        gemini_model = agent_cfg["gemini_model"]
        gemini_voice = agent_cfg["gemini_voice"]
        gemini_cache_key = f"gemini:{gemini_voice}:{clean_text}"
        gemini_digest = hashlib.md5(gemini_cache_key.encode("utf-8")).hexdigest()
        gemini_path = CACHE_DIR / f"{gemini_digest}.mp3"

        if gemini_path.exists() and gemini_path.stat().st_size > 0:
            return gemini_path

        models_to_try = [gemini_model]
        if "gemini-3.8-flash-tts" not in models_to_try:
            models_to_try.append("gemini-3.8-flash-tts")

        for m_name in models_to_try:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                config = types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=gemini_voice
                            )
                        )
                    ),
                )
                response = await client.aio.models.generate_content(
                    model=m_name,
                    contents=clean_text,
                    config=config,
                )

                audio_data: Optional[bytes] = None
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                            audio_data = part.inline_data.data
                            break

                if audio_data:
                    if isinstance(audio_data, str):
                        audio_data = base64.b64decode(audio_data)
                    gemini_path.write_bytes(audio_data)
                    logger.info(f"Áudio sintetizado com sucesso via Gemini TTS ({m_name} - {gemini_voice}) para {agent_normalized}")
                    return gemini_path
            except Exception as e:
                err_str = str(e)
                if "402" in err_str or "429" in err_str:
                    _gemini_quota_exhausted = True
                    logger.warning(
                        f"Cota do Gemini indisponível ({err_str[:60]}...). "
                        f"Ativando modo consistente edge-tts para evitar mistura de vozes."
                    )
                    break
                logger.warning(
                    f"Tentativa de síntese Gemini TTS ({m_name} / {gemini_voice}) falhou: {e}."
                )

    # 2. Fallback Gracioso Obrigatório: edge-tts
    fallback_voice = agent_cfg["edge_fallback"]
    rate = "+0%"
    pitch = "+0Hz"
    edge_cache_key = f"{fallback_voice}:{rate}:{pitch}:{clean_text}"
    edge_digest = hashlib.md5(edge_cache_key.encode("utf-8")).hexdigest()
    edge_path = CACHE_DIR / f"{edge_digest}.mp3"

    if edge_path.exists() and edge_path.stat().st_size > 0:
        return edge_path

    try:
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=fallback_voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(str(edge_path))
        logger.info(f"Áudio sintetizado via edge-tts ({fallback_voice}) para {agent_normalized}")
        return edge_path
    except Exception as e:
        logger.warning(
            f"Erro ao sintetizar com voz {fallback_voice}: {e}. Tentando fallback de emergência Antonio."
        )
        sec_voice = "pt-BR-AntonioNeural"
        sec_key = f"{sec_voice}:{rate}:{pitch}:{clean_text}"
        sec_digest = hashlib.md5(sec_key.encode("utf-8")).hexdigest()
        sec_path = CACHE_DIR / f"{sec_digest}.mp3"

        if sec_path.exists() and sec_path.stat().st_size > 0:
            return sec_path

        sec_comm = edge_tts.Communicate(text=clean_text, voice=sec_voice, rate=rate, pitch=pitch)
        await sec_comm.save(str(sec_path))
        return sec_path


class TTSService:
    """Classe de serviço para manter compatibilidade com instâncias existentes."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key: Optional[str] = os.getenv("GEMINI_API_KEY", "").strip() or None
        self.client: Optional[Any] = None

    def get_agent_config(self, agent_id: str) -> Tuple[str, str, Optional[str]]:
        normalized = agent_id.lower().replace("@", "").strip()
        return AGENT_VOICE_CONFIG.get(normalized, ("pt-BR-AntonioNeural", "+0%", "+0Hz"))

    def get_agent_voice(self, agent_id: str) -> Dict[str, str]:
        normalized = agent_id.lower().replace("@", "").strip()
        return AGENT_VOICES.get(normalized, AGENT_VOICES["sm"])

    def get_status(self) -> Dict[str, Any]:
        return get_tts_status()

    async def synthesize_speech(self, text: str, agent: str = "sm") -> Path:
        return await synthesize_speech(text=text, agent=agent)

    async def synthesize(self, text: str, agent_id: str = "sm") -> bytes:
        audio_path = await synthesize_speech(text=text, agent=agent_id)
        return audio_path.read_bytes()


__all__ = [
    "AGENT_VOICES",
    "AGENT_VOICE_CONFIG",
    "CACHE_DIR",
    "TTSService",
    "clean_text_for_speech",
    "get_tts_status",
    "synthesize_speech",
]
