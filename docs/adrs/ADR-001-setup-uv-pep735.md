# ADR-001: Adoção do uv e PEP 735 para Gestão Determinística de Dependências e Build

* **Status:** Aceito
* **Data:** 2026-10-26
* **Decisores:** David Almeida (Staff Data Engineer / Tech Lead EY)
* **Ticket:** TJR-01 (Épico 01: Fundação & Camada Bronze)

---

## 1. Contexto & Forças Arquiteturais em Tensão

O projeto *Tech Jobs Radar* é uma plataforma de inteligência de mercado desenvolvida com rigor de consultoria Big 4 (EY Technology Consulting — AI & Data Practice). Como sistema analítico, ele combina ingestão assíncrona (`httpx`), validação rigorosa de contratos (`Pydantic v2`), processamento de dados e testes adversariais automatizados.

### Forças e Restrições:
1. **Velocidade de Feedback & Ciclo de Kolb:** O desenvolvimento solo em blocos de até 2 horas exige resolução de dependências em milissegundos, eliminando o atrito cognitivo de ferramentas lentas;
2. **Reprodutibilidade Matemática no CI/CD:** Builds em máquinas locais (Linux/macOS/Windows) e em runners do GitHub Actions devem executar sobre binários idênticos, garantindo determinismo estrito;
3. **Isolamento de Escopo:** Ferramentas de desenvolvimento, análise estática (`ruff`, `mypy`) e testes (`pytest`, `respx`, `hypothesis`) não devem poluir os metadados do pacote instalável de produção;
4. **Alinhamento com Padrões Python Modernos (2024–2026):** Evitar ferramentas que dependem de sintaxes proprietárias ou formatos legados (`setup.py`, múltiplos `requirements-*.txt`).

---

## 2. Alternativas Avaliadas

### Opção 1: Poetry
- *Prós:* Ecossistema maduro, lockfile próprio (`poetry.lock`).
- *Contras:* Resolução de dependências notoriamente lenta em árvores complexas; sintaxe proprietária em `[tool.poetry]` que não segue a PEP 621 nativa; histórico de conflitos com virtualenvs preexistentes.

### Opção 2: pip + pip-tools (`requirements.in` / `requirements.txt`)
- *Prós:* Simples e tradicional.
- *Contras:* Fragmentação em múltiplos arquivos de texto; ausência de um lockfile universal multiplataforma com hashes de todos os ambientes; lentidão em downloads e compilações sequenciais.

### Opção 3: uv (Astral / Rust) + PEP 735 (`[dependency-groups]`)
- *Prós:*
  - Escrito em Rust, performance de 10x a 100x superior às ferramentas existentes;
  - Utiliza o algoritmo PubGrub (CDCL SAT Solver) para resolução instantânea de dependências;
  - Gera um único `uv.lock` determinístico multiplataforma com content-hash SHA-256;
  - Suporta nativamente a **PEP 735 (Dependency Groups in pyproject.toml)**, aprovada em 2024, permitindo compor grupos com `{ include-group = "..." }`;
  - Instalação ultra-rápida via cache global com hardlinks/reflinks (zero duplicação de bytes em disco).
- *Contras:* Ferramenta recente, exigindo que a equipe mantenha o CLI `uv` atualizado.

---

## 3. Decisão Arquitetural

Decidimos adotar o **`uv` (Astral)** como o único gerenciador de ambientes virtuais, ferramentas, runtimes e dependências do monorepo *Tech Jobs Radar*, utilizando o arquivo padrão **`pyproject.toml`** em total conformidade com a **PEP 621** (metadados de projeto) e **PEP 735** (tabela `[dependency-groups]`).

---

## 4. Consequências & Trade-offs

### Consequências Positivas:
- **Resolução e Instalação em Segundos:** Redução do tempo de `uv sync --all-groups` para menos de 3 segundos;
- **Eliminação de Deriva de Ambiente (*Environment Drift*):** O arquivo `uv.lock` versionado no Git garante que os testes no GitHub Actions e no ambiente local rodem com versões e hashes de pacotes rigorosamente idênticos;
- **Clareza de Separação de Dependências:** O código de produção só enxerga `httpx`, `pydantic`, `tenacity` e `python-dotenv`, enquanto ferramentas de lint e teste ficam isoladas em `dependency-groups`;
- **Comandos Determinísticos:** Toda execução é padronizada via `uv run <comando>` sem necessidade de ativação manual de scripts `activate`.

### Trade-offs & Mitigação:
- **Dependência do CLI `uv`:** Mitigado pela facilidade de instalação em comando único (`curl -LsSf https://astral.sh/uv/install.sh | sh`) e suporte oficial no GitHub Actions (`astral-sh/setup-uv@v3`).
