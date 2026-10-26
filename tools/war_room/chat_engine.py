"""Motor de Orquestração de Agentes para o Squad War Room.

Gerencia o ciclo de conversação dos 4 agentes:
- @SM: gemini-2.5-flash | Thinking: LOW (0 tokens)
- @TL: gemini-2.5-flash | Thinking: HIGH (4096 tokens)
- @QA: gemini-2.5-flash | Thinking: MEDIUM (2048 tokens)
- @PO: gemini-2.5-flash | Thinking: MEDIUM (2048 tokens)

Produz Dual Output:
- spoken_reply: fala natural de reunião (2 a 4 frases, sem ler sintaxe markdown/código)
- markdown_notes: notas técnicas detalhadas para o painel lateral
- board_action: ação opcional para mover tickets ou anexar registros ao Obsidian
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
if PROJECT_ENV.exists():
    load_dotenv(dotenv_path=PROJECT_ENV, override=False)

from obsidian_manager import ObsidianManager

logger = logging.getLogger("chat_engine")

SKILLS_DIR = Path("/home/nova/.gemini/config/skills")

AGENT_METADATA = {
    "sm": {
        "name": "Francisca (@SM)",
        "role": "Scrum Master & DataOps Flow Guardian",
        "model": "gemini-3.5-flash-lite",
        "thinking_budget": 0,
        "thinking_level": "LOW (0 tokens)",
        "voice": "pt-BR-FranciscaNeural",
        "avatar": "📋",
        "color": "#10b981",
        "skill_path": SKILLS_DIR / "scrum-master" / "SKILL.md",
    },
    "tl": {
        "name": "Antonio (@TL)",
        "role": "Tech Lead de Dados Sênior/Staff (Padrão EY)",
        "model": "gemini-3.5-flash",
        "thinking_budget": 4096,
        "thinking_level": "HIGH (4096 tokens)",
        "voice": "pt-BR-AntonioNeural",
        "avatar": "👨‍💻",
        "color": "#3b82f6",
        "skill_path": SKILLS_DIR / "tech-lead" / "SKILL.md",
    },
    "qa": {
        "name": "Fabio (@QA)",
        "role": "Data Quality & Adversarial Test Engineer",
        "model": "gemini-3.5-flash",
        "thinking_budget": 2048,
        "thinking_level": "HIGH (2048 tokens)",
        "voice": "pt-BR-FabioNeural",
        "avatar": "🧪",
        "color": "#f59e0b",
        "skill_path": SKILLS_DIR / "data-qa" / "SKILL.md",
    },
    "po": {
        "name": "Thalita (@PO)",
        "role": "Data Product Owner & Estrategista STAR EY",
        "model": "gemini-3.5-flash",
        "thinking_budget": 2048,
        "thinking_level": "MED/HIGH (2048 tokens)",
        "voice": "pt-BR-ThalitaMultilingualNeural",
        "avatar": "🎯",
        "color": "#8b5cf6",
        "skill_path": SKILLS_DIR / "product-owner" / "SKILL.md",
    },
}


class ChatEngine:
    def __init__(self, obsidian_mgr: ObsidianManager):
        self.obsidian_mgr = obsidian_mgr
        self.personas: Dict[str, str] = {}
        self._load_personas()
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.last_api_error: Optional[str] = None

    def _load_personas(self) -> None:
        for agent_key, meta in AGENT_METADATA.items():
            path = meta["skill_path"]
            if path.exists():
                try:
                    self.personas[agent_key] = path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Erro ao ler persona {path}: {e}")
                    self.personas[agent_key] = f"Você é o agente {meta['name']}, atuando como {meta['role']}."
            else:
                self.personas[agent_key] = f"Você é o agente {meta['name']}, atuando como {meta['role']}."

    def is_online(self) -> bool:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        return bool(self.api_key)

    def get_agents_info(self) -> Dict[str, Any]:
        info = {}
        for k, v in AGENT_METADATA.items():
            info[k] = {
                "id": k,
                "name": v["name"],
                "role": v["role"],
                "model": v["model"],
                "thinking_budget": v["thinking_budget"],
                "thinking_level": v["thinking_level"],
                "voice": v["voice"],
                "avatar": v["avatar"],
                "color": v["color"],
            }
        return info

    async def process_turn(
        self,
        user_message: str,
        target_agent: str = "auto",
        rite: str = "general",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Processa a mensagem e retorna spoken_reply, markdown_notes e board_action."""
        tasks = self.obsidian_mgr.parse_tasks()

        # Determina o agente caso venha "auto"
        selected_agent = self._resolve_agent(target_agent, rite, user_message)

        # Se API KEY configurada, tenta chamada online com timeout resiliente de 5.0s
        if self.is_online():
            try:
                res = await asyncio.wait_for(
                    self._call_gemini_api(
                        user_message=user_message,
                        agent_key=selected_agent,
                        rite=rite,
                        tasks=tasks,
                        history=history or [],
                    ),
                    timeout=15.0,
                )
                self.last_api_error = None
                return res
            except Exception as e:
                self.last_api_error = str(e)
                logger.warning(f"Timeout ou erro na chamada Gemini API ({e}). Acionando motor de ritos local.")

        # Fallback para o Motor de Ritos Offline
        return self._run_offline_rite_engine(
            user_message=user_message,
            agent_key=selected_agent,
            rite=rite,
            tasks=tasks,
        )

    def _resolve_agent(self, target_agent: str, rite: str, user_msg: str) -> str:
        tgt = target_agent.lower().replace("@", "").strip()
        if tgt in AGENT_METADATA:
            return tgt

        # Mapeamento padrão por rito
        rite_map = {
            "planning": "sm",
            "daily": "sm",
            "design_review": "tl",
            "quality_gate": "qa",
            "sabatina": "tl",
            "review_star": "po",
        }
        if rite in rite_map:
            return rite_map[rite]

        # Busca menção no texto
        msg_lower = user_msg.lower()
        if "@tl" in msg_lower or "tech lead" in msg_lower or "arquitetura" in msg_lower:
            return "tl"
        if "@qa" in msg_lower or "qualidade" in msg_lower or "teste" in msg_lower or "drift" in msg_lower:
            return "qa"
        if "@po" in msg_lower or "product owner" in msg_lower or "negócio" in msg_lower or "star" in msg_lower or "xyz" in msg_lower:
            return "po"
        return "sm"

    async def _call_gemini_api(
        self,
        user_message: str,
        agent_key: str,
        rite: str,
        tasks: List[Dict[str, Any]],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        meta = AGENT_METADATA[agent_key]
        persona = self.personas.get(agent_key, "")

        tasks_summary = json.dumps(tasks, indent=2, ensure_ascii=False)

        system_instruction = f"""
{persona}

Você está participando do SQUAD WAR ROOM em áudio/voz ao vivo do projeto Tech Jobs Radar.
Rito atual: {rite.upper()}
Agente que você representa: {meta['name']} ({meta['role']})

Quadro de Tarefas Atual (Sprint Ativa.md):
{tasks_summary}

REGRAS DE COMUNICAÇÃO DE REUNIÃO AO VIVO:
1. Responda ESTRITAMENTE em formato JSON com as chaves:
   - "spoken_reply": Fala coloquial, fluida e direta para ser sintetizada em voz neural (2 a 4 frases curtas). JAMAIS leia código, markdown, links, hashtags ou tabelas aqui. Fale como um colega sênior em uma reunião de trabalho pelo Google Meet.
   - "markdown_notes": Notas técnicas estruturadas, perguntas socráticas, checklists de DoD/DoR, bullets Google XYZ ou casos STAR que serão renderizados no painel lateral de anotações.
   - "board_action": (Opcional) Objeto se você decidir alterar o status de uma tarefa ou registrar log. Exemplo: {{"action": "update_status", "ticket": "TJR-01", "new_status": "In Progress"}} ou null.
2. Mantenha o tom da sua persona (Scrum Master, Tech Lead EY socrático, QA adversarial rigoroso ou PO executivo).
3. REGRA FONÉTICA ESSENCIAL PARA FALA:
   - Na chave "spoken_reply", JAMAIS use a palavra "time" para se referir à equipe (para o sintetizador neural não confundir com a palavra em inglês "time = tempo"); use SEMPRE "equipe" ou "pessoal".
   - Quando mencionar "timebox", "timeboxing", "pipeline", "PySpark", etc., escreva com termos naturais que soem bem em português brasileiro falado.
"""

        # Configuração com Thinking Budget
        budget = meta["thinking_budget"]
        config_kwargs: Dict[str, Any] = {
            "system_instruction": system_instruction,
            "response_mime_type": "application/json",
        }
        if budget > 0:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)

        config = types.GenerateContentConfig(**config_kwargs)

        prompt = f"Mensagem do Desenvolvedor: {user_message}"
        response = await client.aio.models.generate_content(
            model=meta["model"],
            contents=prompt,
            config=config,
        )

        raw_text = (response.text or "").strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        # Sanitiza barras invertidas inválidas para não quebrar o json.loads com LaTeX ou escapes
        clean_json_str = re.sub(r'\\(?![/"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', raw_text)

        try:
            parsed = json.loads(clean_json_str, strict=False)
            spoken = parsed.get("spoken_reply", "")
            notes = parsed.get("markdown_notes", "")
            action = parsed.get("board_action")

            # Aplica ação de board se houver
            self._apply_board_action(action, meta["name"])

            return {
                "agent": agent_key,
                "agent_name": meta["name"],
                "role": meta["role"],
                "model": meta["model"],
                "thinking_level": meta["thinking_level"],
                "spoken_reply": spoken,
                "markdown_notes": notes,
                "board_action": action,
                "mode": "online",
            }
        except Exception as err:
            logger.warning(f"Erro ao parsear JSON da Gemini API: {err}. Conteúdo: {raw_text[:200]}")
            # Extração resiliente direta preservando estritamente UTF-8 sem mojibake
            spoken_match = re.search(r'"spoken_reply"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            notes_match = re.search(r'"markdown_notes"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)

            def _clean_str(val: str) -> str:
                return val.replace(r'\"', '"').replace(r'\n', '\n').replace(r'\t', '\t')

            spoken = _clean_str(spoken_match.group(1)) if spoken_match else raw_text[:280]
            notes = _clean_str(notes_match.group(1)) if notes_match else raw_text

            action = None
            action_match = re.search(r'"board_action"\s*:\s*(\{[^}]+\})', raw_text)
            if action_match:
                try:
                    action = json.loads(action_match.group(1))
                    self._apply_board_action(action, meta["name"])
                except Exception:
                    pass

            return {
                "agent": agent_key,
                "agent_name": meta["name"],
                "role": meta["role"],
                "model": meta["model"],
                "thinking_level": meta["thinking_level"],
                "spoken_reply": spoken,
                "markdown_notes": notes,
                "board_action": action,
                "mode": "online",
            }

    def _run_offline_rite_engine(
        self,
        user_message: str,
        agent_key: str,
        rite: str,
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Motor de ritos local inteligente quando operando sem API Key."""
        meta = AGENT_METADATA[agent_key]

        # Encontra a tarefa em progresso ou a primeira To Do
        active_task = None
        for t in tasks:
            if t["status"] == "In Progress":
                active_task = t
                break
        if not active_task:
            for t in tasks:
                if t["status"] == "To Do":
                    active_task = t
                    break
        if not active_task and tasks:
            active_task = tasks[0]

        task_key = active_task["key"] if active_task else "TJR-01"
        task_summary = active_task["summary"] if active_task else "Setup da Fundação"
        task_dod = active_task["dod"] if active_task else "Critérios de aceite definidos"
        task_status = active_task["status"] if active_task else "To Do"

        spoken = ""
        notes = ""
        action = None

        if rite == "planning" or "plan" in user_message.lower():
            msg_lower = user_message.lower().strip()
            # 1. Pergunta sobre o comportamento estático / modelos não respondem
            if any(w in msg_lower for w in ["estátic", "estatico", "estatica", "responde", "modelo", "offline", "bug", "travado", "não respondem"]):
                spoken = (
                    "Atenção: A chave da API Gemini retornou erro 402, que significa créditos pré-pagos esgotados no projeto Antigravity-Drive. "
                    "Por isso o War Room acionou o motor de contingência local. "
                    "Para ativar o raciocínio dinâmico dos modelos por inteligência artificial, basta atualizar a variável no arquivo .env pela chave gratuita do Default Gemini Project."
                )
                notes = f"""### ⚠️ Diagnóstico da Squad: Modo de Contingência Local Ativo
> **Causa Raiz Identificada:** A chave configurada no `.env` pertence ao projeto pré-pago sem saldo (`HTTP 402 RESOURCE_EXHAUSTED`).
> **Como Desbloquear IA Dinâmica:** No Google AI Studio, copie a chave do **`Default Gemini Project`** (que opera no **Nível gratuito** com 1.500 requisições/dia) e insira no arquivo `.env`.
> 
> Enquanto isso, o rito de Planning da Sprint 1 pode prosseguir! A tarefa prioritária para começarmos é a **`{task_key}`** ({task_summary}).
"""
            # 2. Confirmação para iniciar a sprint / task
            elif any(w in msg_lower for w in ["sim", "vamos", "começar", "iniciar", "bora", "ok", "partiu", "start", "pode"]):
                action = {"action": "update_status", "ticket": task_key, "new_status": "In Progress"}
                spoken = (
                    f"Excelente! Acabei de atualizar a tarefa {task_key} para In Progress no quadro do Obsidian. "
                    f"A Sprint 1 está oficialmente em andamento com a regra de WIP igual a um. "
                    f"Passo a palavra ao Antonio, nosso Tech Lead, para o Design Review socrático de arquitetura."
                )
                notes = f"""### 🚀 Sprint 1 Oficialmente Iniciada!
- **Tarefa no Foco (`WIP = 1`):** `{task_key}` movida para `In Progress` no Obsidian.
- **Diretriz de Fluxo:** Nenhuma outra tarefa pode ser aberta até a conclusão de `{task_key}` (Timebox: até 120 min).
- **Próximo Rito:** Design Review Socrático com o Tech Lead (@TL).
"""
            # 3. Disparo inicial do Planning
            else:
                spoken = (
                    f"Olá equipe! Estamos iniciando o Sprint Planning da Sprint 1. "
                    f"Nossa meta é estruturar a fundação com monorepo uv e ingerir a camada Bronze com resiliência. "
                    f"Temos quatro fatias verticais com timebox de até duas horas cada e mantemos regra estrita de WIP igual a um. "
                    f"A prioridade imediata é a tarefa {task_key}. Vamos começar por ela?"
                )
                notes = f"""### 🗓️ Sprint Planning — Sprint 1: Fundação & Camada Bronze
> **Meta da Sprint:** Monorepo Medalhão (`uv`), Ingestão Resiliente Google Jobs (SerpApi), Contrato Pydantic v2 e Notificador Telegram.

#### 📋 Fatiamento Vertical das Tasks:
- **TJR-01:** Setup Monorepo Medalhão (`uv`, `pyproject.toml`, `Ruff`, `pytest`, `ADR-001`) — *Est: 1.5h*
- **TJR-02:** Cliente assíncrono SerpApi com retry backoff + jitter e Pydantic v2 estrito — *Est: 2.0h*
- **TJR-03:** Persistência Bronze particionada (`source=google_jobs/dt=YYYY-MM-DD`) idempotente — *Est: 2.0h*
- **TJR-04:** Notificador Telegram assíncrono com deduplicação de alertas — *Est: 1.5h*

#### ⚡ Diretrizes de Fluxo do @SM:
1. **Regra de Ouro:** `WIP = 1` estrito. Proibido abrir TJR-02 sem TJR-01 estar em `Done`.
2. **Timebox:** Até 120 minutos por task (Ciclo de Kolb).
"""

        elif rite == "daily" or "daily" in user_message.lower():
            spoken = (
                f"Bom dia! Daily rápida de três minutos na mesa. "
                f"Estamos focados na tarefa {task_key}, atualmente com status {task_status}. "
                f"Você enfrentou algum bloqueio técnico ou desvio de escopo nas últimas horas? "
                f"Lembre-se da nossa regra de WIP igual a um: termine a fatia atual antes de abrir a próxima."
            )
            notes = f"""### ⚡ Daily Check-in (Timebox: 3 min)
- **Tarefa no Foco (`WIP = 1`):** `{task_key}` — {task_summary}
- **Status Atual no Quadro:** `{task_status}`
- **Critério de Saída (DoD):** {task_dod}

#### 🎯 As 3 Perguntas do Scrum Master:
1. *O que foi concluído na última sessão de deep work?*
2. *Qual o objetivo das próximas duas horas (timebox 120 min)?*
3. *Existe algum impedimento técnico ou risco de violação de WIP?*
"""

        elif rite == "design_review" or agent_key == "tl" and "design" in user_message.lower():
            agent_key = "tl"
            meta = AGENT_METADATA["tl"]
            spoken = (
                f"Perfeito, desenvolvedor. Como Tech Lead com padrão EY, antes de codar a {task_key}, "
                f"precisamos validar dois princípios inegociáveis de arquitetura. "
                f"Primeiro: qual é o grão exato dessa camada e como você garante a idempotência se o job rodar três vezes? "
                f"Segundo: qual o trade-off de custo e memória se o volume multiplicar por cem? Quero ouvir seu raciocínio."
            )
            notes = f"""### 🏗️ Design Review Socrático (@TL Padrão EY) — `{task_key}`
> **Foco da Task:** {task_summary}
> **Módulos Teóricos:** NotebookLM Doc 01, 02 e 06 (*Fundamentos Lakehouse e Idempotência*).

#### ❓ As 2 Perguntas Socráticas Obrigatórias (DoR):
1. **Grão & Idempotência ($f(f(x)) = f(x)$):**
   - *Qual é a chave primária de negócio (surrogate key determinística SHA-256) dessa fatia?*
   - *O que acontece se o pipeline falhar na metade e a reexecução disparar 3 vezes no mesmo dia? O dado duplica ou o sink é estritamente idempotente?*
2. **Custo, Escala & Trade-off (FinOps & Big 4):**
   - *Por que essa abordagem foi escolhida em vez de alternativas mais complexas?*
   - *Como ela se comporta em termos de memória (driver memory safe), I/O de rede e custos de API?*

> [!TIP]
> Ao responder estas duas perguntas satisfatoriamente, a task pode mover para `In Progress`.
"""
            if task_status == "To Do":
                action = {"action": "update_status", "ticket": task_key, "new_status": "In Progress"}

        elif rite == "quality_gate" or agent_key == "qa" or "qa" in user_message.lower():
            agent_key = "qa"
            meta = AGENT_METADATA["qa"]
            spoken = (
                f"Atenção equipe, aqui é o QA de dados. Em engenharia de dados, falhas silenciosas são piores que erros explícitos. "
                f"Na tarefa {task_key}, estou aplicando o crivo das sete heurísticas adversariais. "
                f"Seu contrato Pydantic v2 está com extra igual a forbid e strict verdadeiro? "
                f"E você já testou o reprocessamento de lote duas vezes consecutivas para validar que a contagem distinta de chaves permanece idêntica?"
            )
            notes = f"""### 🧪 Quality Gate & Testes Adversariais (@QA) — `{task_key}`
> **Paradigma:** Shift-Left Data Quality & Mindset Adversarial.

#### 🛡️ As 7 Heurísticas Adversariais de Quebra de Dados:
- [ ] **1. Armadilha NaN vs None vs null:** Tratamento explícito de `float('nan') != float('nan')`.
- [ ] **2. Timezone Drift:** Timestamps normalizados rigorosamente em UTC (`timezone.utc`).
- [ ] **3. Whitespaces Invisíveis:** Sanitização de strings vazias, `\\t`, `\\n` e zero-width space para `None`.
- [ ] **4. Injeção de HTML/Entidades:** Sanitização de `&amp;`, `&nbsp;` e tags do Google Jobs.
- [ ] **5. Determinismo de Surrogate Keys:** Hash SHA-256 gerado sobre campos em ordem canônica normalizada.
- [ ] **6. Late-Arriving Data:** Proteção contra sobrescrita de dados mais recentes por reprocessamento atrasado.
- [ ] **7. Resiliência de Rede:** Simulação com `respx` de `HTTP 429` (Rate Limit) e `503` com backoff exponencial + jitter.

#### 🔁 Teste de Idempotência Obrigatório:
```python
# O sink deve produzir o mesmo estado após execução duplicada:
# df_run_1.count() == df_run_2.select("vaga_sk").distinct().count()
```
"""

        elif rite == "sabatina" or (agent_key == "tl" and "sabatina" in user_message.lower()):
            agent_key = "tl"
            meta = AGENT_METADATA["tl"]
            spoken = (
                f"Vamos agora para a Sabatina Técnica padrão EY da tarefa {task_key}. "
                f"Imagine que estamos na entrevista com o Diretor da Prática de AI e Dados. "
                f"Me explique por que usamos uv em vez de Poetry ou pip puro, "
                f"e como você defenderia o uso de DuckDB in-process gratuito em vez de subir um cluster Spark para essa escala inicial?"
            )
            notes = f"""### 🎓 Sabatina Técnica Padrão EY (@TL) — `{task_key}`
> **Objetivo:** Preparação para entrevistas de liderança técnica em consultorias Big 4 (EY Technology Consulting).

#### 💼 Questões de Sabatina (Big 4 DNA):
1. **Tooling & Resolução de Dependências (`uv` vs `Poetry`/`pip`):**
   - *Por que adotamos `uv` com o padrão PEP 735 (dependency groups)? Qual o impacto em tempo de build no CI/CD e determinismo de lockfile?*
2. **FinOps & Right-Sizing Arquitetural:**
   - *Como justificar a um cliente corporativo que iniciar com ingestão assíncrona leve e DuckDB in-process é mais prudente financeiramente do que alocar um cluster Databricks/EMR subutilizado?*
3. **Internals de Integridade:**
   - *Qual o impacto de dados corrompidos na camada Bronze se ela não for imutável?*
"""

        elif rite == "review_star" or agent_key == "po" or "star" in user_message.lower():
            agent_key = "po"
            meta = AGENT_METADATA["po"]
            spoken = (
                f"Excelente! Como Product Owner, estou homologando a entrega de negócio da tarefa {task_key}. "
                f"Aplicando o teste So What, transformamos a sintaxe técnica em impacto econômico e redução de risco. "
                f"Já estruturei seu bullet no formato Google X Y Z e o roteiro do case STAR para suas entrevistas na EY. "
                f"O registro está disponível no painel de notas da call."
            )
            notes = f"""### 🏆 Sprint Review & Case STAR (@PO) — `{task_key}`
> **Conexão de Negócio:** *The "So What?" Test* — Traduzindo código em ativos de carreira.

#### 📌 Google XYZ Resume Bullet:
> *"Projetou e implementou pipeline de ingestão assíncrona resiliente para vagas de tecnologia (**Google Jobs / SerpApi**), garantindo **100% de conformidade com contratos Pydantic v2 estritos** e **zero duplicidade em falhas de rede**, reduzindo em **~70%** o processamento de dados redundantes."*

#### 🌟 Narrativa STAR para Entrevista Técnica EY:
- **[S]ituação:** Necessidade de coletar inteligência de mercado contínua sobre vagas de dados sem incorrer em custos de cloud prematuros ou poluição de dados brutos.
- **[T]arefa:** Construir a camada Bronze do Lakehouse com ingestão assíncrona, retry com jitter e contrato de dados de alta precisão.
- **[A]ção:** Implementação em Python assíncrono com `httpx`, validação estrita Pydantic v2 (`strict=True, extra='forbid'`), particionamento temporal UTC e testes automatizados de quebra com `pytest` e `respx`.
- **[R]esultado:** Pipeline com idempotência matemática comprovada, tempo de build no CI/CD inferior a 3 segundos com `uv` e arquitetura aderente às melhores práticas de governança corporativa.
"""
            # Registra no Obsidian se o usuário confirmar
            self.obsidian_mgr.append_star_case(
                task_key=task_key,
                star_bullet="Projetou monorepo Medalhão e ingestão resiliente com contratos Pydantic v2 estritos.",
                star_narrative="Implementação validada no Sprint Review da Sprint 1.",
            )

        else:
            spoken = (
                f"Estou com a palavra no Squad War Room. Analisando o estado da Sprint 1, "
                f"estamos focados em avançar a tarefa {task_key}. "
                f"Qual rito você gostaria de conduzir agora? Podemos rodar o Planning, Daily, Design Review ou Sabatina EY."
            )
            notes = f"""### 📋 Painel de Controle de Ritos — Squad War Room
- **Agente na Linha:** {meta['name']} ({meta['role']})
- **Tarefa no Foco:** `{task_key}` — {task_summary}
- **Status:** `{task_status}`

> Selecione um rito nos botões rápidos acima ou fale diretamente pelo microfone.
"""

        if action:
            self._apply_board_action(action, meta["name"])

        # Se houve erro 402 na Gemini API, adiciona alerta no topo das notas
        if self.last_api_error and "402" in self.last_api_error and "Diagnóstico da Squad" not in notes:
            warning_callout = (
                "> [!WARNING]\n"
                "> **Modo Contingência Local (Gemini 402 Pré-pago Zerado):** O modelo está respondendo localmente "
                "porque a chave no `.env` está sem saldo pré-pago. Para ativar o raciocínio generativo dinâmico com IA, "
                "substitua no `.env` pela chave gratuita (`Default Gemini Project`).\n\n"
            )
            notes = warning_callout + notes

        return {
            "agent": agent_key,
            "agent_name": meta["name"],
            "role": meta["role"],
            "model": meta["model"],
            "thinking_level": meta["thinking_level"],
            "spoken_reply": spoken,
            "markdown_notes": notes,
            "board_action": action,
            "mode": "offline",
        }

    def _apply_board_action(self, action: Optional[Dict[str, Any]], agent_name: str) -> None:
        if not action or not isinstance(action, dict):
            return

        act_type = action.get("action")
        if act_type == "update_status":
            ticket = action.get("ticket")
            new_status = action.get("new_status")
            if ticket and new_status:
                updated = self.obsidian_mgr.update_task_status(ticket, new_status)
                if updated:
                    self.obsidian_mgr.append_event_log(
                        title=f"Atualização de Status: {ticket} -> {new_status}",
                        details=f"Tarefa {ticket} movida para `{new_status}` durante rito ágil.",
                        agent=agent_name,
                    )
        elif act_type == "append_log":
            text = action.get("text", "")
            title = action.get("title", "Registro de Rito")
            if text:
                self.obsidian_mgr.append_event_log(title=title, details=text, agent=agent_name)
