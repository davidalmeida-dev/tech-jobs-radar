"""Testes de Verificação do Setup do Monorepo e Arquitetura Medalhão (TJR-01).

Valida a conformidade da árvore de diretórios, pacotes internos,
configurações PEP 735, variáveis de ambiente seguras e documentação de ADRs.
"""

import tomllib
from pathlib import Path


def test_core_packages_are_importable():
    """Valida que todos os pacotes da arquitetura Medalhão são importáveis."""
    import src
    import src.bronze
    import src.contracts
    import src.gold
    import src.ingestion
    import src.serving
    import src.silver

    assert src.__version__ == "0.1.0"
    assert src.contracts.__doc__ is not None
    assert src.ingestion.__doc__ is not None
    assert src.bronze.__doc__ is not None
    assert src.silver.__doc__ is not None
    assert src.gold.__doc__ is not None
    assert src.serving.__doc__ is not None


def test_medallion_directory_structure_exists():
    """Valida a existência dos diretórios físicos do Data Lakehouse e governança."""
    root_dir = Path(__file__).resolve().parents[2]

    required_dirs = [
        root_dir / "src" / "contracts",
        root_dir / "src" / "ingestion",
        root_dir / "src" / "bronze",
        root_dir / "src" / "silver",
        root_dir / "src" / "gold",
        root_dir / "src" / "serving",
        root_dir / "data" / "bronze",
        root_dir / "data" / "silver",
        root_dir / "data" / "gold",
        root_dir / "data" / "quarantine",
        root_dir / "docs" / "adrs",
        root_dir / "tests" / "unit",
    ]

    for directory in required_dirs:
        assert directory.exists(), f"Diretório mandatório ausente: {directory}"
        assert directory.is_dir(), f"Caminho não é um diretório: {directory}"


def test_env_example_contains_all_required_keys():
    """Valida que o template seguro .env.example declara todas as variáveis de produção."""
    root_dir = Path(__file__).resolve().parents[2]
    env_example = root_dir / ".env.example"

    assert env_example.exists(), "Arquivo .env.example não encontrado na raiz."
    content = env_example.read_text(encoding="utf-8")

    required_keys = [
        "SERPAPI_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GEMINI_API_KEY",
        "DATA_LAKE_BASE_PATH",
    ]

    for key in required_keys:
        assert f"{key}=" in content, f"Chave mandatória ausente no .env.example: {key}"


def test_pyproject_conforms_to_pep_735_and_ruff():
    """Valida que o pyproject.toml declara PEP 735 [dependency-groups] e [tool.ruff]."""
    root_dir = Path(__file__).resolve().parents[2]
    pyproject_path = root_dir / "pyproject.toml"

    assert pyproject_path.exists(), "pyproject.toml não encontrado na raiz."
    with pyproject_path.open("rb") as f:
        config = tomllib.load(f)

    # Validação do core
    assert config["project"]["name"] == "tech-jobs-radar"
    assert "httpx" in str(config["project"]["dependencies"])
    assert "pydantic" in str(config["project"]["dependencies"])

    # Validação da PEP 735 (dependency-groups)
    assert "dependency-groups" in config, "Tabela [dependency-groups] da PEP 735 ausente."
    dep_groups = config["dependency-groups"]
    assert "dev" in dep_groups
    assert "lint" in dep_groups
    assert "test" in dep_groups

    # Validação do Ruff
    assert "tool" in config and "ruff" in config["tool"], "Configuração [tool.ruff] ausente."
    assert config["tool"]["ruff"]["line-length"] == 100


def test_adr_001_document_exists_and_is_accepted():
    """Valida que a ADR-001 de decisão do uv/PEP 735 está devidamente registrada."""
    root_dir = Path(__file__).resolve().parents[2]
    adr_path = root_dir / "docs" / "adrs" / "ADR-001-setup-uv-pep735.md"

    assert adr_path.exists(), "ADR-001 não encontrada em docs/adrs/."
    content = adr_path.read_text(encoding="utf-8")
    assert "Status: Aceito" in content or "Status:** Aceito" in content
    assert "PEP 735" in content
    assert "uv" in content
