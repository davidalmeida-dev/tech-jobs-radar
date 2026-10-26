# 🎯 Tech Jobs Radar

> **Radar Autônomo de Inteligência de Mercado e Oportunidades em Engenharia de Dados**  
> *Padrão de Excelência Big 4 (EY Technology Consulting — AI & Data Practice)*

---

## 🏛️ Arquitetura Medalhão & Visão do Monorepo

O **Tech Jobs Radar** é uma plataforma orientada a dados construída sob os princípios modernos de **DataOps, Lakehouse Medalhão e Shift-Left Data Quality**:

- **🥉 Camada Bronze (`src/bronze`):** Ingestão resiliente e imutável (*append-only*) de dados brutos com particionamento Hive (`source=google_jobs/dt=YYYY-MM-DD/`) e metadados de auditoria em UTC estrito.
- **🥈 Camada Silver (`src/silver`):** Higienização, deduplicação transacional (`MERGE INTO`), isolamento de *Schema Drift* em Quarentena (*Dead Letter Queue*) e extração de skills com *FlashText Trie O(N)* + *Gemini API*.
- **🥇 Camada Gold (`src/gold`):** Modelagem Dimensional de Kimball (*Star Schema* com Bridge Table $N:N$), agregações analíticas vetorizadas em *DuckDB* e cálculo do *Match Score XAI*.
- **🚀 Serving (`src/serving`):** Alertas assíncronos no Telegram Bot e Data App Executivo em *Streamlit*.

---

## 🛠️ Tooling & Stack Tecnológico

- **Gerenciador de Runtimes & Pacotes:** [`uv`](https://docs.astral.sh/uv/) (Astral / Rust) com lockfile determinístico `uv.lock`.
- **Organização de Dependências:** Padrão [PEP 735](https://peps.python.org/pep-0735/) (`[dependency-groups]` para `dev`, `lint` e `test`).
- **Linter & Formatter:** [`Ruff`](https://docs.astral.sh/ruff/) com análise estática de AST em Rust.
- **Contratos de Dados:** [`Pydantic v2`](https://docs.pydantic.dev/) em modo estrito (`strict=True`, `extra="forbid"`).
- **Testes & Mocks:** `pytest`, `pytest-asyncio` e `respx` (mocks de rede sem tocar a internet).

---

## 🚀 Inicialização Rápida

```bash
# 1. Sincronizar todas as dependências e criar o ambiente virtual
uv sync --all-groups

# 2. Executar validação de qualidade de código
uv run ruff check .

# 3. Executar suíte completa de testes
uv run pytest -vv
```
