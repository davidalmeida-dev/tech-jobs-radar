#!/usr/bin/env bash
# ==============================================================================
# Script de Inicialização Rápida • Squad War Room (Tech Jobs Radar)
# Ambiente Apartado de Ritos com Voz Neural Gratuita + Chat Multi-Agente
# ==============================================================================

set -e

WAR_ROOM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8765
HOST="0.0.0.0"

echo "================================================================================"
echo "🚀 INICIANDO SQUAD WAR ROOM — TECH JOBS RADAR"
echo "================================================================================"
echo "📁 Diretório: $WAR_ROOM_DIR"
echo "🌐 Endereço:  http://localhost:$PORT"
echo "🎙️ Vozes:     edge-tts (pt-BR Francisca, Antonio, Fabio, Thalita) [0 tokens áudio]"
echo "🧠 Agentes:   @SM (Thinking: LOW) | @TL (HIGH) | @QA (MED) | @PO (MED)"
echo "📋 Vault:     Obsidian Live Sync (Sprint Ativa.md + Log de Ritos & Sabatinas.md)"
echo "--------------------------------------------------------------------------------"

# 1. Verifica se a porta já está em uso
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Porta $PORT já está em uso! Finalizando processo anterior..."
    kill -9 $(lsof -t -i:$PORT) 2>/dev/null || true
    sleep 1
fi

# 2. Carrega .env do projeto se existir
PROJECT_ENV="$WAR_ROOM_DIR/../../.env"
if [ -f "$PROJECT_ENV" ]; then
    echo "🔑 Carregando variáveis de $PROJECT_ENV..."
    export $(grep -v '^#' "$PROJECT_ENV" | xargs)
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "ℹ️  GEMINI_API_KEY não detectada. Ativando Motor de Ritos Local (Modo Demo Offline)."
    echo "💡 Para conectar os agentes ao Gemini 3.8 Flash Online, defina GEMINI_API_KEY no seu .env."
else
    echo "✅ GEMINI_API_KEY detectada! Agentes conectados online via Gemini 3.8 Flash & Gemini 3.8 TTS."
fi

echo "--------------------------------------------------------------------------------"
echo "🔥 Acesse agora: http://localhost:$PORT"
echo "   (Pressione Ctrl+C para encerrar a War Room)"
echo "================================================================================"

cd "$WAR_ROOM_DIR"
exec python3 -m uvicorn server:app --host "$HOST" --port "$PORT" --reload
