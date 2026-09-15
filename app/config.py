"""应用配置：环境变量 + 模型注册表（models.yaml）加载。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录（app/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env（不存在时静默跳过，测试环境可用环境变量注入）
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """基础运行配置（全部来自环境变量 / .env）。"""

    # LLM
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "deepseek-chat"))

    # Embedding（默认）
    embedding_model_id: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_ID", "qwen3-embedding-8b"))

    # 向量库
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))

    # 检索
    default_top_k: int = field(default_factory=lambda: int(os.getenv("DEFAULT_TOP_K", "5")))
    relevance_threshold: float = field(default_factory=lambda: float(os.getenv("RELEVANCE_THRESHOLD", "0.35")))

    # 数据目录（原始教材 / 处理缓存）
    data_dir: Path = BASE_DIR / "data"
    raw_dir: Path = BASE_DIR / "data" / "raw"
    processed_dir: Path = BASE_DIR / "data" / "processed"

    # 认证（账户体系，缺失 JWT_SECRET 时启动即报错，防默认密钥上线）
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_expires_days: int = field(default_factory=lambda: int(os.getenv("JWT_EXPIRES_DAYS", "7")))

    # 注册邀请码（外人不许随意注册）：为空 = 禁止注册；注册时必须匹配该码
    register_invite_code: str = field(default_factory=lambda: os.getenv("REGISTER_INVITE_CODE", ""))

    # 系统管理员引导密码（高危操作权限）：为空 = 不自动创建 admin；
    # 配置后启动时若无 admin 用户则自动创建（username=admin, is_admin=1）
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))


class ModelRegistry:
    """模型注册表：解析 models.yaml，Key 一律从环境变量读取，不落配置文件。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (BASE_DIR / "models.yaml")
        if not self.path.exists():
            raise FileNotFoundError(f"模型注册表不存在: {self.path}")
        data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self._chat_models: dict[str, dict] = {m["id"]: m for m in data.get("chat_models", [])}
        self._embedding_models: dict[str, dict] = {m["id"]: m for m in data.get("embedding_models", [])}

    # ---- LLM ----
    def chat_model_ids(self) -> list[str]:
        return list(self._chat_models.keys())

    def chat_model(self, model_id: str) -> dict:
        """返回 {id, name, base_url, model, api_key_env, api_key}。未知 id 抛 KeyError。"""
        m = self._chat_models[model_id]
        return {**m, "api_key": self._resolve_key(m["api_key_env"])}

    def chat_model_info(self, model_id: str) -> dict:
        """只读元数据（不含 Key，供 /health、前端下拉使用）。"""
        m = self._chat_models[model_id]
        return {"id": m["id"], "name": m["name"], "model": m["model"]}

    # ---- Embedding ----
    def embedding_model_ids(self) -> list[str]:
        return list(self._embedding_models.keys())

    def embedding_model(self, model_id: str) -> dict:
        m = self._embedding_models[model_id]
        return {**m, "api_key": self._resolve_key(m["api_key_env"])}

    def embedding_model_info(self, model_id: str) -> dict:
        m = self._embedding_models[model_id]
        return {"id": m["id"], "name": m["name"], "model": m["model"], "dimensions": m.get("dimensions")}

    @staticmethod
    def _resolve_key(env_name: str) -> str:
        key = os.getenv(env_name, "").strip()
        if not key:
            raise RuntimeError(f"缺少环境变量 {env_name}（在 .env 中配置对应 API Key）")
        return key


_settings: Settings | None = None
_registry: ModelRegistry | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry