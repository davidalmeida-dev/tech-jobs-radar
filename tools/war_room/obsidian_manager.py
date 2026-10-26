"""Gerenciador de leitura e escrita do estado ágil e ritos no Obsidian Vault.

Lê e atualiza diretamente:
- 00 - Agile & Sprints/Sprint Ativa.md
- 00 - Agile & Sprints/Log de Ritos & Sabatinas.md
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_POSSIBLE_VAULT_PATHS = [
    Path("/home/nova/Documentos/Vaults/Study/Cursos/Engenharia de Dados/Projetos/Tech Jobs Radar/00 - Agile & Sprints"),
    Path("/home/nova/Documentos/Obsidian Vault/Cursos/Engenharia de Dados/Projetos/Tech Jobs Radar/00 - Agile & Sprints"),
]

DEFAULT_VAULT_PATH = next((p for p in _POSSIBLE_VAULT_PATHS if p.exists()), _POSSIBLE_VAULT_PATHS[0])
SPRINT_ATIVA_FILE = DEFAULT_VAULT_PATH / "Sprint Ativa.md"
LOG_RITOS_FILE = DEFAULT_VAULT_PATH / "Log de Ritos & Sabatinas.md"


class ObsidianManager:
    def __init__(self, vault_dir: Path | str = DEFAULT_VAULT_PATH):
        self.vault_dir = Path(vault_dir)
        self.sprint_ativa_path = self.vault_dir / "Sprint Ativa.md"
        self.log_ritos_path = self.vault_dir / "Log de Ritos & Sabatinas.md"

    def read_sprint_ativa_raw(self) -> str:
        if self.sprint_ativa_path.exists():
            return self.sprint_ativa_path.read_text(encoding="utf-8")
        return self._fallback_sprint_ativa()

    def parse_tasks(self) -> List[Dict[str, Any]]:
        content = self.read_sprint_ativa_raw()
        tasks: List[Dict[str, Any]] = []

        # Tabela markdown com colunas:
        # | Key | Épico | Resumo da Tarefa (Fatia Vertical) | Status | Est. | Branch | Critério de Aceite (`DoD` Binário) |
        table_pattern = re.compile(
            r"\|\s*\*\*(TJR-\d+)\*\*\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*`([^`]+)`\s*\|\s*([^|]+)\|",
            re.MULTILINE,
        )

        for match in table_pattern.finditer(content):
            key = match.group(1).strip()
            epic = match.group(2).strip()
            summary = match.group(3).strip()
            status = match.group(4).strip()
            est = match.group(5).strip()
            branch = match.group(6).strip()
            dod = match.group(7).strip()

            tasks.append(
                {
                    "key": key,
                    "epic": epic,
                    "summary": summary,
                    "status": status,
                    "estimate": est,
                    "branch": branch,
                    "dod": dod,
                }
            )

        return tasks

    def update_task_status(self, task_key: str, new_status: str) -> bool:
        """Atualiza o status de uma task diretamente no arquivo markdown."""
        if not self.sprint_ativa_path.exists():
            return False

        content = self.sprint_ativa_path.read_text(encoding="utf-8")

        # Padrão para capturar a linha da tarefa e substituir seu status `Status Antigo`
        pattern = re.compile(
            rf"(\|\s*\*\*{re.escape(task_key)}\*\*\s*\|[^|]+\|[^|]+\|\s*)`[^`]+`(\s*\|[^|]+\|[^|]+\|[^|]+\|)"
        )

        if not pattern.search(content):
            return False

        new_content = pattern.sub(rf"\1`{new_status}`\2", content)
        self.sprint_ativa_path.write_text(new_content, encoding="utf-8")
        return True

    def read_logs_raw(self) -> str:
        if self.log_ritos_path.exists():
            return self.log_ritos_path.read_text(encoding="utf-8")
        return "# Log de Ritos\nNenhum registro ainda."

    def append_event_log(self, title: str, details: str, agent: str = "@SM") -> bool:
        """Adiciona um evento append-only no final da seção de Histórico de Eventos."""
        if not self.log_ritos_path.exists():
            return False

        content = self.log_ritos_path.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_entry = (
            f"\n- **[{today}] {title} ({agent}):**\n"
            f"  {details.strip()}\n"
        )

        if "## 🗓️ Histórico de Eventos" in content:
            parts = content.split("## 🏆 Banco de Cases STAR")
            if len(parts) == 2:
                updated = parts[0].rstrip() + "\n" + new_entry + "\n---\n\n## 🏆 Banco de Cases STAR" + parts[1]
                self.log_ritos_path.write_text(updated, encoding="utf-8")
                return True

        # Fallback append no final
        content = content.rstrip() + "\n" + new_entry
        self.log_ritos_path.write_text(content, encoding="utf-8")
        return True

    def append_star_case(self, task_key: str, star_bullet: str, star_narrative: str) -> bool:
        """Registra caso STAR gerado pelo @PO no final do arquivo."""
        if not self.log_ritos_path.exists():
            return False

        content = self.log_ritos_path.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")

        entry = (
            f"\n### 🎯 [{today}] {task_key} — Case STAR Homologado pelo @PO\n"
            f"**Google XYZ Bullet:**\n> {star_bullet.strip()}\n\n"
            f"**Narrativa STAR (Entrevista Técnica EY):**\n"
            f"{star_narrative.strip()}\n\n---\n"
        )

        content = content.rstrip() + "\n" + entry
        self.log_ritos_path.write_text(content, encoding="utf-8")
        return True

    def _fallback_sprint_ativa(self) -> str:
        return """# 🔥 Sprint Ativa — Sprint 1
| Key | Épico | Resumo da Tarefa (Fatia Vertical) | Status | Est. | Branch | Critério de Aceite (`DoD` Binário) |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **TJR-01** | `EPIC-01: Bronze` | Setup Monorepo Medalhão (`uv`, `pyproject.toml` PEP 735, `Ruff`, `pytest`, `ADR-001`) | `To Do` | 1.5h | `chore/TJR-01-project-setup` | `uv run ruff check` + `uv run pytest` limpos + árvore Medalhão/DLQ + `.env.example` |
| **TJR-02** | `EPIC-01: Bronze` | Cliente assíncrono Google Jobs (SerpApi) com `httpx`, backoff + jitter e Contrato Pydantic v2 (`strict=True`) | `To Do` | 2.0h | `feat/TJR-02-serpapi-client` | Paginação + retry `HTTP 429/5xx` + testes `respx` + rejeição de schema drift |
| **TJR-03** | `EPIC-01: Bronze` | Persistência Bronze particionada (`source=google_jobs/dt=YYYY-MM-DD`) com metadados UTC e idempotência | `To Do` | 2.0h | `feat/TJR-03-bronze-writer` | Escrita idempotente + metadados (`_ingested_at` UTC, `_batch_id`) + teste de reexecução 2x |
| **TJR-04** | `EPIC-01: Bronze` | Notificador assíncrono Telegram Bot (`sendMessage`) com deduplicação de alertas enviados | `To Do` | 1.5h | `feat/TJR-04-telegram-notifier` | Alerta formatado sem repetir vagas já notificadas + mock `respx` para API do Telegram |
"""
