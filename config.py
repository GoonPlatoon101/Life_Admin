import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    working_dir: Path


class ConfigError(RuntimeError):
    pass


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ConfigError(f"Missing required environment variable: {name}")

    return value.strip()


def _optional_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def load_config(working_dir: Path | None = None) -> Config:
    resolved_working_dir = working_dir or Path.cwd()
    _load_env_file(resolved_working_dir / ".env")

    return Config(
        llm_api_key=_required_env("LLM_API_KEY"),
        llm_base_url=_optional_env("LLM_BASE_URL", "http://localhost:11434/v1"),
        llm_model=_optional_env("LLM_MODEL", "qwen3"),
        working_dir=resolved_working_dir,
    )
