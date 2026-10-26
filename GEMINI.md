# Regras de Orquestração Autônoma, Paralelismo Contract-First & Amarração de Modelos — Tech Jobs Radar

- **Repositório de Código Pessoal:** `/home/nova/Projetos-Pessoais/tech-jobs-radar` (Isolado com `davidgralmeida@gmail.com` e `~/.ssh/id_ed25519_pessoal`).
- **Diretório de Gestão Ágil no Obsidian:** `/home/nova/Documentos/Obsidian Vault/Cursos/Engenharia de Dados/Projetos/Tech Jobs Radar/`
- **GitHub CLI Pessoal:** Sempre executar comandos `gh` com `env -u GITHUB_TOKEN gh` (ou alias `ghp`) para não utilizar o token corporativo da Brasilseg.
- **Squad War Room (Ambiente Apartado de Voz & Ritos):** `/home/nova/Projetos-Pessoais/tech-jobs-radar/tools/war_room/` (`http://localhost:8765`)

---

## 1. Protocolo Permanente do Manager (`Argon`) — *Contract-First Parallelism*
1. **Definição de Contrato (`Argon`):** O Manager define assinaturas, contratos Pydantic/JSON e propriedade estrita de arquivos em $\le 15$ linhas.
2. **Execução Paralela (`Subagentes Flash`):** Dispare simultaneamente via `invoke_subagent` (`Model: "flash"`):
   - **Worker 1 (`Core/Backend`):** Implementa `src/pipelines/...` ou `src/contracts/...`
   - **Worker 2 (`Serving/Frontend`, se houver):** Implementa `src/serving/...` ou `static/...`
   - **Worker 3 (`Blind Adversarial @QA`):** Escreve `tests/` em paralelo baseado exclusivamente no contrato e nas **7 Heurísticas de Quebra** (sem viés de confirmação).
3. **Gate de Integração:** Executa `uv run ruff check .` + `uv run pytest -vv` para validar a junção.

## 2. Amarração de Modelos e Níveis de Raciocínio por Agente
- **`📋 @SM` (`scrum-master`):** `gemini-3.5-flash-lite` + `thinking_level="LOW"` (Voz: `pt-BR-FranciscaNeural`) — Latência $<1\text{s}$ e leitura exclusiva de `Sprint Ativa.md`.
- **`🧪 @QA` (`data-qa`):** `gemini-3.8-flash` + `thinking_level="HIGH"` (Voz: `pt-BR-FabioNeural`) — Execução rigorosa de `uv run pytest`, `ruff` e 7 Heurísticas Adversariais.
- **`🎯 @PO` (`product-owner`):** `gemini-3.8-flash` + `thinking_level="MEDIUM/HIGH"` (Voz: `pt-BR-ThalitaNeural`).
- **`👨‍💻 @TL` (`tech-lead`):** `Argon Med / gemini-3.8-flash` + `thinking_level="HIGH"` (Voz: `pt-BR-AntonioNeural`) — Design Review socrático, veto a anti-padrões PySpark/Delta e Sabatina Técnica EY.

## 3. Pipeline Automática em Cadeia (`WIP = 1` & Ciclo de Kolb 120m)
- **Ao iniciar `TJR-XX`:** `@SM` move para `In Progress` $\rightarrow$ `@TL` conduz Design Review (2 perguntas socráticas).
- **Ao concluir `TJR-XX`:** `@QA` (testes + Ruff) $\rightarrow$ `@TL` (PR Review + 1 pergunta de Sabatina EY) $\rightarrow$ `@SM` (move para `Done`) $\rightarrow$ `@PO` (gera Bullet Google XYZ + Case STAR em `Log de Ritos & Sabatinas.md`).
