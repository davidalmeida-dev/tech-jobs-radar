#!/usr/bin/env python3
"""Script de Benchmark Acústico e Geração em Massa para a Squad Tech Jobs Radar.

Executa a síntese de voz dos 4 textos reais dos ritos da Squad:
- @SM (Francisca / Kore): Rito de Sprint Planning da Sprint 1
- @TL (Antonio / Charon): Rito de Design Review Socrático & Sabatina EY
- @QA (Fabio / Fenrir): Rito de Quality Gate & Testes Adversariais
- @PO (Thalita / Aoede): Rito de Sprint Review & Carreira EY

Mede métricas de engenharia acústica:
- Latência de síntese (segundos)
- Tamanho do arquivo gerado (bytes)
- Duração exata do áudio (segundos)
- Contagem de palavras e cadência (WPM - Words Per Minute)
- Fator de Tempo Real (RTF - Real-Time Factor)
- Normalização fonética (antes e depois de clean_text_for_speech)

Salva arquivos de áudio em tools/war_room/benchmark_audio/ e o relatório em JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Carrega .env do projeto se existir
PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from mutagen.mp3 import MP3
from tts_service import AGENT_VOICES, clean_text_for_speech, synthesize_speech

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("acoustic_benchmark")

OUTPUT_DIR = Path(__file__).parent / "benchmark_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Definição canônica dos 4 textos reais de ritos da Squad
BENCHMARK_CASES: List[Dict[str, str]] = [
    {
        "agent": "sm",
        "rito": "sprint_planning",
        "title": "Rito de Sprint Planning da Sprint 1 (@SM - Francisca / Kore)",
        "raw_text": (
            "Bom dia, equipe! Estamos abrindo oficialmente a Sprint Planning da nossa Sprint 1 do Tech Jobs Radar. "
            "A meta inegociável desta sprint é construir o Walking Skeleton com o setup do monorepo Medalhão em uv, "
            "Ruff e pytest, a ingestão resiliente de vagas do Google Jobs via SerpApi, e a persistência na camada Bronze "
            "particionada no padrão Hive dt=YYYY-MM-DD com notificação de novas vagas no Telegram.\n\n"
            "Para proteger seu foco entre os estudos da UNIFEI e o trabalho corporativo na Brasilseg, o nosso working agreement "
            "é sagrado: regra de WIP igual a um estrito e timebox máximo de duas horas por fatia vertical, cobrindo de "
            "TJR-01 a TJR-04. Cada bloco segue as 4 fases do Ciclo de Kolb: quinze minutos de design review socrático com o Antonio, "
            "setenta minutos de deep work focado, vinte minutos de validação adversarial com o Fábio e quinze minutos de fechamento e sabatina.\n\n"
            "Antonio, a TJR-01 já está pronta para o seu design review. Vamos manter o fluxo enxuto e começar puxando o primeiro card!"
        ),
    },
    {
        "agent": "tl",
        "rito": "design_review",
        "title": "Rito de Design Review Socrático da TJR-01 & Sabatina EY (@TL - Antonio / Charon)",
        "raw_text": (
            "Perfeito, David. Antes de você abrir o editor para codar a TJR-01, vamos fazer o nosso Design Review técnico com "
            "ancoragem de OLTP para OLAP e o crivo de excelência da EY. No backend transacional com PostgreSQL, você pensa em linhas, "
            "índices B-Tree e constraints ACID. No nosso Data Lakehouse, o paradigma muda: pensamos em colunas, compressão Snappy, "
            "particionamento Hive e processamento em lote idempotente.\n\n"
            "Minha primeira pergunta socrática para o seu DoR: qual é o grão exato da camada Bronze e o que acontece se o pipeline "
            "reexecutar três vezes seguidas após uma falha de rede? A ingestão precisa ser estritamente idempotente, com metadados UTC "
            "e controle de batch ID para evitar duplicação downstream.\n\n"
            "E na nossa Sabatina técnica EY sobre PySpark Internals: se o volume da SerpApi crescer cem vezes, como o Catalyst Optimizer "
            "e o Tungsten evitam um Out of Memory no Driver? Jamais faremos collect cego ou loop de withColumn; exploraremos narrow "
            "transformations, projeções colunares e off-heap memory management para manter o custo baixo e o pipeline escalável. "
            "Está autorizado a puxar a branch da TJR-01!"
        ),
    },
    {
        "agent": "qa",
        "rito": "quality_gate",
        "title": "Rito de Quality Gate & Testes Adversariais (@QA - Fabio / Fenrir)",
        "raw_text": (
            "Fala, David! Fábio na área para o Quality Gate e a suíte de testes adversariais da Squad. Em Engenharia de Dados, "
            "falhas silenciosas e corrupção de dados são muito mais destrutivas do que exceções explícitas. Aqui nosso crivo é implacável: "
            "nada sobe para a Silver sem passar pelos contratos Pydantic v2 estritos com extra forbid e validação de tipos em tempo de execução.\n\n"
            "Se a SerpApi introduzir schema drift upstream ou campos nulos inesperados, o registro é desviado automaticamente para a nossa "
            "Dead Letter Queue auditável, sem quebrar o processamento em lote nem contaminar a camada limpa.\n\n"
            "No pytest, aplicamos o teste de idempotência duas vezes consecutivas com o mesmo lote: a contagem de registros e chaves surrogates "
            "sha-256 no destino deve ser rigorosamente invariante após a reexecução. Além disso, nosso pipeline de CI/CD no GitHub Actions "
            "bloqueia qualquer commit que contenha credenciais ou tokens em texto claro. Código limpo no Ruff, cem por cento de aprovação "
            "nos contratos e portão de qualidade aprovado!"
        ),
    },
    {
        "agent": "po",
        "rito": "sprint_review",
        "title": "Rito de Sprint Review & Carreira EY (@PO - Thalita / Aoede)",
        "raw_text": (
            "Olá, David! Chegamos à nossa Sprint Review da Sprint 1 e à homologação de valor de negócio para posicionamento executivo "
            "na prática de AI e Data da EY. Mais do que código rodando, avaliamos o retorno econômico e o impacto de produto. "
            "Nosso motor de recomendação combina FinOps e Inteligência Artificial com precisão: usamos a Trie do FlashText em CPU "
            "com complexidade O de N para filtrar hard skills em memória, economizando setenta por cento de chamadas pagas à Gemini API "
            "com Structured Outputs determinísticos.\n\n"
            "O cálculo multivariado do nosso Match Score pondera hard skills, aderência semântica e senioridade com explicabilidade total, "
            "sem efeito de caixa preta.\n\n"
            "E para o seu portfólio executivo e preparação com sócios da EY, já consolidei a entrega dupla no log do Obsidian: "
            "o Bullet no padrão Google XYZ destacando a redução de TCO e latência sub-segundo, acompanhado da narrativa completa "
            "no método STAR detalhando o desafio de arquitetura, a decisão técnica e os resultados mensuráveis de governança. "
            "Parabéns pela entrega, valor homologado com sucesso!"
        ),
    },
]


def get_audio_duration_seconds(file_path: Path) -> float:
    """Calcula a duração exata do arquivo de áudio (compatível com WAV do Gemini e MP3 do edge-tts)."""
    # 1. Tenta decodificar como RIFF WAVE (formato nativo retornado pela Gemini API)
    try:
        with wave.open(str(file_path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate > 0:
                return round(frames / float(rate), 2)
    except Exception:
        pass

    # 2. Tenta decodificar como MPEG Audio / MP3 (formato retornado pelo fallback edge-tts)
    try:
        audio = MP3(str(file_path))
        if audio.info and audio.info.length:
            return round(float(audio.info.length), 2)
    except Exception:
        pass

    return 0.0


async def run_benchmark() -> Dict[str, Any]:
    """Executa a síntese de áudio para cada caso e compila o relatório de benchmark."""
    print("=" * 80)
    print("🎯 BENCHMARK ACÚSTICO — TECH JOBS RADAR SQUAD")
    print(f"Diretório de Saída: {OUTPUT_DIR.resolve()}")
    print(f"Data & Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    results: List[Dict[str, Any]] = []

    for index, case in enumerate(BENCHMARK_CASES, start=1):
        agent_key = case["agent"]
        rito_key = case["rito"]
        title = case["title"]
        raw_text = case["raw_text"]

        # 1. Normalização Fonética
        clean_text = clean_text_for_speech(raw_text)
        word_count = len(clean_text.split())

        voice_info = AGENT_VOICES.get(agent_key, AGENT_VOICES["sm"])

        print(f"\n[{index}/4] {title}")
        print("-" * 80)
        print("📄 TEXTO ORIGINAL:")
        print(raw_text.strip())
        print("\n🗣️ TEXTO NORMALIZADO (FONÉTICA PT-BR):")
        print(clean_text)
        print(f"\n⚙️ Configuração da Voz: Gemini={voice_info['gemini_voice']} | Fallback={voice_info['edge_fallback']}")
        print(f"📊 Contagem de Palavras: {word_count} palavras")

        # 2. Síntese com medição de tempo
        t_start = time.perf_counter()
        cached_audio_path = await synthesize_speech(raw_text, agent_key)
        generation_time = round(time.perf_counter() - t_start, 3)

        # 3. Cópia para o diretório canônico do benchmark
        dest_filename = f"{agent_key}_{rito_key}.mp3"
        dest_path = OUTPUT_DIR / dest_filename
        shutil.copy2(cached_audio_path, dest_path)

        file_size_bytes = dest_path.stat().st_size
        file_size_kb = round(file_size_bytes / 1024, 2)

        # 4. Cálculo de Duração e Velocidade Acústica
        duration_seconds = get_audio_duration_seconds(dest_path)
        if duration_seconds > 0:
            wpm = round((word_count / duration_seconds) * 60, 1)
            words_per_sec = round(word_count / duration_seconds, 2)
            rtf = round(generation_time / duration_seconds, 3)
        else:
            wpm = 0.0
            words_per_sec = 0.0
            rtf = 0.0

        # Identificação do motor real usado (pelo cabeçalho do arquivo)
        header_sample = dest_path.read_bytes()[:12]
        if header_sample.startswith(b"RIFF") and b"WAVE" in header_sample:
            engine_used = f"Gemini 3.8 Flash-Lite TTS ({voice_info['gemini_voice']}) [RIFF/WAV Container]"
        else:
            engine_used = f"edge-tts ({voice_info['edge_fallback']}) [MPEG/MP3 Container]"

        entry = {
            "agent": agent_key,
            "rito": rito_key,
            "title": title,
            "filename": dest_filename,
            "file_path": str(dest_path.resolve()),
            "engine_used": engine_used,
            "voice_config": voice_info,
            "word_count": word_count,
            "generation_time_sec": generation_time,
            "audio_duration_sec": duration_seconds,
            "file_size_bytes": file_size_bytes,
            "file_size_kb": file_size_kb,
            "words_per_minute": wpm,
            "words_per_second": words_per_sec,
            "real_time_factor": rtf,
            "text_before_normalization": raw_text,
            "text_after_normalization": clean_text,
        }
        results.append(entry)

        print(f"⏱️ Tempo de Síntese: {generation_time}s | Duração do Áudio: {duration_seconds}s")
        print(f"📦 Tamanho: {file_size_kb} KB ({file_size_bytes} bytes)")
        print(f"🚀 Velocidade Acústica: {wpm} WPM ({words_per_sec} palavras/seg)")
        print(f"⚡ Real-Time Factor (RTF): {rtf}x (quanto menor, mais rápido que o tempo real)")
        print(f"🎙️ Motor Identificado: {engine_used}")
        print(f"💾 Arquivo Salvo: {dest_path}")

    # Relatório Final
    report: Dict[str, Any] = {
        "benchmark_timestamp": datetime.now().isoformat(),
        "total_audios": len(results),
        "output_directory": str(OUTPUT_DIR.resolve()),
        "audios": results,
    }

    report_path = OUTPUT_DIR / "benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 80)
    print(f"✅ RELATÓRIO SALVO COM SUCESSO: {report_path.resolve()}")
    print("=" * 80)

    # Tabela Resumo
    print("\n📋 RESUMO EXECUTIVO DO BENCHMARK:")
    print(
        f"{'Agente':<8} | {'Voz':<22} | {'Palavras':<9} | {'Síntese':<8} | {'Duração':<8} | {'WPM':<8} | {'Tamanho (KB)':<12} | {'Arquivo':<24}"
    )
    print("-" * 115)
    for r in results:
        voice_label = r["voice_config"]["gemini_voice"] + " / " + r["voice_config"]["edge_fallback"].split("-")[2].replace("Neural", "")
        print(
            f"{r['agent'].upper():<8} | {voice_label:<22} | {r['word_count']:<9} | {r['generation_time_sec']:>6.2f}s | {r['audio_duration_sec']:>6.1f}s | {r['words_per_minute']:>6.1f} | {r['file_size_kb']:>10.1f}  | {r['filename']:<24}"
        )
    print("-" * 115)

    return report


if __name__ == "__main__":
    asyncio.run(run_benchmark())
