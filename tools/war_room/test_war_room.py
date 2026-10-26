"""Testes automatizados e adversariais do Squad War Room.

Valida sob o paradigma Shift-Left Data Quality e Blind Adversarial Testing:
- Contrato AGENT_VOICES (Gemini 3.8 Flash-Lite TTS + Fallback edge-tts + 4 vozes únicas)
- Endpoint /api/state (status, agentes, tasks do Obsidian e motor de voz configurado)
- Endpoint /api/chat (Dual Output: spoken_reply + markdown_notes)
- Endpoint /api/tts (Síntese para os 4 agentes e resiliência com fallback)
- Endpoint /api/board/update (Sincronização com Sprint Ativa.md)
- Heurísticas Adversariais: chave Gemini inválida/ausente, HTML injection, entidades e whitespaces invisíveis.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

import tts_service
from server import app

# ==============================================================================
# 1. Validação Estrita do Contrato Técnico de Vozes (tts_service.AGENT_VOICES)
# ==============================================================================


def test_agent_voices_contract():
    """Valida o contrato técnico inviolável de AGENT_VOICES:

    - Deve conter as 4 chaves: 'sm', 'tl', 'qa', 'po'
    - Cada configuração deve ter:
        * gemini_model == 'gemini-3.8-flash-lite-tts'
        * gemini_voice dentre {'Kore', 'Charon', 'Fenrir', 'Aoede'}
        * 4 vozes distintas sem colisão
        * edge_fallback configurado
    """
    assert hasattr(tts_service, "AGENT_VOICES"), (
        "tts_service deve exportar o dicionário AGENT_VOICES"
    )

    voices_cfg = tts_service.AGENT_VOICES
    expected_agents = {"sm", "tl", "qa", "po"}
    assert expected_agents.issubset(set(voices_cfg.keys())), (
        f"AGENT_VOICES deve conter as chaves {expected_agents}"
    )

    expected_gemini_voices = {"Kore", "Charon", "Fenrir", "Aoede"}
    found_gemini_voices = []

    for agent in expected_agents:
        cfg = voices_cfg[agent]
        model = cfg["gemini_model"] if isinstance(cfg, dict) else cfg.gemini_model
        voice = cfg["gemini_voice"] if isinstance(cfg, dict) else cfg.gemini_voice
        fallback = cfg["edge_fallback"] if isinstance(cfg, dict) else cfg.edge_fallback

        assert model == "gemini-3.8-flash-lite-tts", (
            f"Agente '{agent}' deve usar 'gemini-3.8-flash-lite-tts', obteve '{model}'"
        )
        assert voice in expected_gemini_voices, (
            f"Voz '{voice}' do agente '{agent}' deve ser uma das vozes Gemini suportadas: {expected_gemini_voices}"
        )
        assert fallback, f"Agente '{agent}' deve possuir edge_fallback configurado"
        found_gemini_voices.append(voice)

    # Verifica se as 4 vozes são únicas sem colisão
    assert len(set(found_gemini_voices)) == 4, (
        f"As 4 vozes devem ser únicas sem colisão! Obtidas: {found_gemini_voices}"
    )
    assert set(found_gemini_voices) == expected_gemini_voices


# ==============================================================================
# 2. Validação do Estado da Squad e Configuração TTS (/api/state)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_state():
    """Valida o estado completo do War Room: status, badges de thinking, modelos e tarefas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/state")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "online"
        assert "agents" in data
        assert "sm" in data["agents"]
        assert "tl" in data["agents"]
        assert "qa" in data["agents"]
        assert "po" in data["agents"]

        # Verifica badges de thinking amarrados por agente
        assert data["agents"]["sm"]["thinking_budget"] == 0
        assert data["agents"]["tl"]["thinking_budget"] == 4096
        assert data["agents"]["qa"]["thinking_budget"] == 2048
        assert data["agents"]["po"]["thinking_budget"] == 2048

        # Verifica modelos amarrados por responsabilidade
        assert data["agents"]["sm"]["model"] == "gemini-3.5-flash-lite"
        assert data["agents"]["tl"]["model"] in ("gemini-3.8-flash", "gemini-3.5-flash")
        assert data["agents"]["qa"]["model"] in ("gemini-3.8-flash", "gemini-3.5-flash")
        assert data["agents"]["po"]["model"] in ("gemini-3.8-flash", "gemini-3.5-flash")

        # Verifica tasks do Obsidian
        assert "tasks" in data
        assert len(data["tasks"]) >= 4
        keys = [t["key"] for t in data["tasks"]]
        assert "TJR-01" in keys
        assert "TJR-02" in keys


@pytest.mark.asyncio
async def test_get_state_tts_contract():
    """Valida se /api/state expõe a configuração do motor TTS primário."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/state")
        assert response.status_code == 200
        data = response.json()

        assert "tts" in data, "GET /api/state deve conter a chave 'tts'"
        tts_info = data["tts"]
        assert isinstance(tts_info, dict), "'tts' deve ser um dicionário"
        assert tts_info.get("primary_engine") == "gemini-3.8-flash-lite-tts", (
            f"Esperado primary_engine == 'gemini-3.8-flash-lite-tts', obteve '{tts_info.get('primary_engine')}'"
        )


# ==============================================================================
# 3. Dual Output Chat Multi-Agente (/api/chat)
# ==============================================================================


@pytest.mark.asyncio
async def test_chat_dual_output_planning():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "Vamos alinhar a meta da Sprint 1 e os timeboxes",
            "agent": "sm",
            "rite": "planning",
        }
        response = await client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "spoken_reply" in data
        assert len(data["spoken_reply"]) > 20
        assert "markdown_notes" in data
        assert len(data["markdown_notes"]) > 50
        assert data["agent"] == "sm"
        assert "Francisca" in data["agent_name"]


@pytest.mark.asyncio
async def test_chat_dual_output_design_review_tl():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "Quero fazer o design review antes de codar a TJR-01",
            "agent": "tl",
            "rite": "design_review",
        }
        response = await client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["agent"] == "tl"
        assert "Antonio" in data["agent_name"]
        assert any(
            t in data["markdown_notes"]
            for t in ["Idempotência", "idempotência", "Grão", "grão", "Reprodutibilidade", "Arquitetura", "Design Review", "DoR"]
        )


@pytest.mark.asyncio
async def test_chat_dual_output_qa_heuristics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "Como testamos as heurísticas adversariais?",
            "agent": "qa",
            "rite": "quality_gate",
        }
        response = await client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert any(k in data["markdown_notes"] for k in ["Adversariais", "Data Quality", "Heurísticas"])


# ==============================================================================
# 4. Síntese TTS Básica para os 4 Agentes (/api/tts)
# ==============================================================================


@pytest.mark.asyncio
async def test_tts_synthesis_all_agents():
    """Valida síntese com retorno de bytes de áudio para os 4 agentes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for ag in ["sm", "tl", "qa", "po"]:
            response = await client.get(
                f"/api/tts?agent={ag}&text=Teste+de+voz+neural+do+agente+{ag}"
            )
            assert response.status_code == 200, (
                f"Falha na síntese do agente {ag}: {response.text}"
            )
            assert "audio" in response.headers.get("content-type", "")
            assert len(response.content) > 500, (
                f"Áudio gerado para {ag} tem apenas {len(response.content)} bytes"
            )


# ==============================================================================
# 5. Testes Adversariais de Fallback e Resiliência (Zero Crashes / HTTP 500)
# ==============================================================================


@pytest.mark.asyncio
async def test_tts_fallback_on_invalid_gemini_key(monkeypatch):
    """Simula falha na autenticação da Gemini API via chave inválida.

    O serviço NUNCA deve retornar HTTP 500; deve acionar o fallback
    (edge-tts) e responder HTTP 200 com bytes válidos (> 500 bytes).
    """
    monkeypatch.setenv("GEMINI_API_KEY", "invalid_key_simulated_failure")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/tts?agent=tl&text=Teste+de+resiliencia+com+chave+invalida"
        )
        assert response.status_code == 200, (
            f"Esperado fallback com 200, obteve {response.status_code}: {response.text}"
        )
        assert "audio" in response.headers.get("content-type", "")
        assert len(response.content) > 500, (
            f"Bytes de áudio insuficientes no fallback: {len(response.content)}"
        )


@pytest.mark.asyncio
async def test_tts_fallback_on_missing_gemini_key(monkeypatch):
    """Simula ausência completa de GEMINI_API_KEY.

    Deve fazer fallback transparente para edge-tts com HTTP 200.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/tts?agent=sm&text=Teste+de+fallback+sem+chave+de+api"
        )
        assert response.status_code == 200, (
            f"Esperado 200 no fallback sem chave, obteve {response.status_code}: {response.text}"
        )
        assert len(response.content) > 500


@pytest.mark.asyncio
async def test_tts_adversarial_dirty_text_sanitization():
    """Valida sanitização contra injeção de HTML, tags de script, entidades e whitespaces invisíveis.

    Heurística Adversarial #3 (Whitespaces Invisíveis: \\u200b) e #4 (Injeção HTML / Entidades &amp;).
    """
    transport = ASGITransport(app=app)
    adversarial_text = (
        "Olá &amp; <script>alert('hack')</script> PySpark \u200b com espaços   "
        " extras e quebra\n\nde linha!"
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET endpoint
        get_res = await client.get(
            "/api/tts", params={"agent": "qa", "text": adversarial_text}
        )
        assert get_res.status_code == 200, (
            f"Falha no GET com texto adversarial: {get_res.text}"
        )
        assert len(get_res.content) > 500

        # POST endpoint
        post_res = await client.post(
            "/api/tts", json={"agent": "po", "text": adversarial_text}
        )
        assert post_res.status_code == 200, (
            f"Falha no POST com texto adversarial: {post_res.text}"
        )
        assert len(post_res.content) > 500


def test_clean_text_for_speech_adversarial_heuristics():
    """Validação unitária da função de sanitização de texto para fala."""
    from tts_service import clean_text_for_speech

    raw = (
        "Olá &amp; <script>alert('x')</script> PySpark \u200b `código_inline`"
        " **negrito** [link](https://test.com)\n# Titulo\n## Subtitulo"
    )
    cleaned = clean_text_for_speech(raw)

    assert "<script>" not in cleaned
    assert "</script>" not in cleaned
    assert "`" not in cleaned
    assert "**" not in cleaned
    assert "#" not in cleaned
    assert "https://" not in cleaned
    assert ("Pai Spark" in cleaned or "PySpark" in cleaned)
    assert len(cleaned.strip()) > 0


@pytest.mark.asyncio
async def test_tts_unknown_agent_graceful_fallback():
    """Agente inexistente ou não mapeado deve usar voz padrão sem quebrar a API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/tts?agent=hacker_unknown_99&text=Teste+agente+desconhecido"
        )
        assert response.status_code == 200
        assert len(response.content) > 500


# ==============================================================================
# 6. Sincronização e Atualização do Quadro (/api/board/update)
# ==============================================================================


@pytest.mark.asyncio
async def test_board_update_and_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Altera status do TJR-01
        res1 = await client.post(
            "/api/board/update",
            json={"ticket": "TJR-01", "status": "In Progress"},
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True

        # Confere se /api/state reflete a mudança
        state_res = await client.get("/api/state")
        state_data = state_res.json()
        tjr01 = next(t for t in state_data["tasks"] if t["key"] == "TJR-01")
        assert tjr01["status"] == "In Progress"

        # Restaura para To Do
        res2 = await client.post(
            "/api/board/update", json={"ticket": "TJR-01", "status": "To Do"}
        )
        assert res2.status_code == 200
