"""Alias para tts_service.py para compatibilidade direta."""

from tts_service import (
    AGENT_VOICE_CONFIG,
    AGENT_VOICES,
    CACHE_DIR,
    TTSService,
    clean_text_for_speech,
    get_tts_status,
    synthesize_speech,
)

__all__ = [
    "AGENT_VOICES",
    "AGENT_VOICE_CONFIG",
    "CACHE_DIR",
    "TTSService",
    "clean_text_for_speech",
    "get_tts_status",
    "synthesize_speech",
]
