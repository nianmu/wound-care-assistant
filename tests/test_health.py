"""健康检查冒烟测试（M1）。"""
import os

# 测试前不依赖 .env；保证能加载模型注册表即可
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("SILICONFLOW_API_KEY", "sk-test-placeholder")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["default_model"] == "deepseek-chat"
        # 模型清单不含任何 Key 字段
        assert "api_key" not in str(body)
        chat_ids = [m["id"] for m in body["models"]["chat"]]
        assert "deepseek-chat" in chat_ids


def test_registry_rejects_missing_key():
    """models.yaml 中已声明的模型若环境缺 Key，取用时必须报错（防静默裸奔）。"""
    from app.config import get_registry

    reg = get_registry()
    # 挑一个未在测试环境设置 Key 的模型
    for mid in reg.chat_model_ids():
        env = reg.chat_model(mid)["api_key_env"] if False else None  # 语义说明
        break
    # 直接验证：命中缺 Key 的模型时抛 RuntimeError
    missing = [mid for mid in reg.chat_model_ids() if not os.getenv(reg._chat_models[mid]["api_key_env"])]
    for mid in missing:
        try:
            reg.chat_model(mid)
            assert False, f"{mid} 缺 Key 却未报错"
        except RuntimeError:
            pass