"""账户体系测试：注册/登录/鉴权/限速/存量迁移/考试模块鉴权（不调用外部 API）。"""
import os
import shutil

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test")
os.environ.setdefault("SILICONFLOW_API_KEY", "sk-test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")
os.environ.setdefault("REGISTER_INVITE_CODE", "test-code")  # 注册邀请码（防随意注册）
os.environ.setdefault("CHROMA_PERSIST_DIR", "./.test_chroma")
os.environ.setdefault("DATA_DIR", "./.test_data")

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import router as auth_router
from app.auth import security
from app.exam import store


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """每个测试独立 sqlite + 清空登录限速计数。"""
    db_file = tmp_path / "exam.db"
    monkeypatch.setattr(store, "_db_path", lambda: db_file)
    monkeypatch.setattr(auth_router, "_FAIL_COUNT", {})
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _register(client, username="mama", password="abc12345", display_name=None, invite_code="test-code"):
    payload = {"username": username, "password": password, "invite_code": invite_code}
    if display_name:
        payload["display_name"] = display_name
    return client.post("/api/auth/register", json=payload)


# ---------- 密码哈希与 JWT（纯函数） ----------

def test_security_hash_and_verify():
    h = security.hash_password("abc12345")
    assert h != "abc12345" and h.startswith("$2")
    assert security.verify_password("abc12345", h)
    assert not security.verify_password("wrong-pass", h)
    assert not security.verify_password("abc12345", "not-a-bcrypt-hash")  # 畸形哈希不炸


def test_security_token_roundtrip():
    t = security.create_token(7, "mama")
    payload = security.decode_token(t)
    assert payload["sub"] == "7" and payload["name"] == "mama"
    assert security.decode_token("garbage.token.here") is None
    assert security.decode_token(t + "x") is None  # 篡改签名


# ---------- 注册 / 登录 / me ----------

def test_register_login_me(client):
    r = _register(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["is_first"] is True
    assert body["user"]["username"] == "mama"
    assert "password_hash" not in str(body)  # 绝不返回哈希

    # me 带 token
    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert r2.status_code == 200 and r2.json()["user"]["username"] == "mama"

    # 登录
    r3 = client.post("/api/auth/login", json={"username": "mama", "password": "abc12345"})
    assert r3.status_code == 200 and r3.json()["token"]

    # 无 token / 坏 token → 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_register_validation(client):
    assert _register(client, username="MAMA1").status_code == 200  # 大写→小写化
    assert _register(client, username="mama1").status_code == 400  # 重复用户名
    assert _register(client, username="a", password="abc12345").status_code == 400   # 用户名过短
    assert _register(client, username="bad_name!", password="abc12345").status_code == 400  # 非法字符
    assert _register(client, username="newuser", password="short").status_code == 400  # 密码过短
    assert _register(client, username="newuser", password="onlyletters").status_code == 400  # 无数字
    assert _register(client, username="newuser2", password="12345678").status_code == 400  # 无字母


def test_login_fail_then_lock(client):
    # 错密码 5 次 → 第 6 次即使密码正确也被锁（429）
    for i in range(5):
        r = client.post("/api/auth/login", json={"username": "mama", "password": "wrong-pass"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"username": "mama", "password": "wrong-pass"})
    assert r.status_code == 429
    # 正确的密码此刻也被锁
    _register(client)
    r2 = client.post("/api/auth/login", json={"username": "mama", "password": "abc12345"})
    assert r2.status_code == 429
    # 换个用户名不受影响（IP 也计数了……先清限速验证用户名维度）
    auth_router._FAIL_COUNT.clear()
    r3 = client.post("/api/auth/login", json={"username": "mama", "password": "abc12345"})
    assert r3.status_code == 200


# ---------- 注册邀请码（防外人随意注册） ----------

def test_register_requires_invite_code(client):
    # 无邀请码 → 403
    r = client.post("/api/auth/register", json={"username": "ma", "password": "abc12345"})
    assert r.status_code == 403
    # 错误邀请码 → 403
    r = _register(client, username="ma", invite_code="wrong-code")
    assert r.status_code == 403
    assert "邀请码" in r.json()["detail"]
    # 正确邀请码 → 200
    assert _register(client, username="mama", invite_code="test-code").status_code == 200
    # 邀请码不区分首尾空白
    r2 = _register(client, username="mama2", invite_code="  test-code  ")
    assert r2.status_code == 200


def test_register_disabled_when_code_unset(client, monkeypatch):
    """安全默认：REGISTER_INVITE_CODE 未配置 → 禁止注册（防止忘了配导致开放）。"""
    fake = SimpleNamespace(register_invite_code="")
    monkeypatch.setattr(auth_router, "get_settings", lambda: fake)
    r = _register(client, username="mama", invite_code="test-code")
    assert r.status_code == 403
    assert "未开放" in r.json()["detail"]


# ---------- 系统管理员（高危操作：上传/删除教材） ----------

def test_admin_ensure_and_normal_user_count():
    adm = store.ensure_admin(security.hash_password("admin-pass"))
    assert adm["username"] == "admin" and adm["is_admin"] == 1
    # 幂等：重复调用返回同一个管理员
    assert store.ensure_admin(security.hash_password("other-pass"))["id"] == adm["id"]
    assert store.normal_user_count() == 0
    store.create_user("mama", "h", "妈妈")
    assert store.normal_user_count() == 1  # admin 不算普通用户


def test_admin_does_not_block_first_normal_user(client):
    """管理员先存在时，第一个普通用户注册仍是 is_first（接管历史数据权不变）。"""
    store.ensure_admin(security.hash_password("admin-pass"))
    r = _register(client, username="mama")
    assert r.status_code == 200
    assert r.json()["is_first"] is True


def test_admin_only_upload_and_delete(client):
    # 普通用户 + 未登录
    _register(client, username="mama")
    tok = client.post("/api/auth/login", json={"username": "mama", "password": "abc12345"}).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    files = {"file": ("t.txt", b"hello", "text/plain")}
    assert client.post("/api/upload", files=files, headers=H).status_code == 403       # 普通用户 403
    assert client.post("/api/upload", files=files).status_code == 401                   # 未登录 401
    assert client.delete("/api/documents/whatever", headers=H).status_code == 403       # 普通用户 403
    assert client.delete("/api/documents/whatever").status_code == 401

    # 管理员：权限放行 → 业务校验层（.pdf 格式 400；删除不存在的来源 200/0）
    store.ensure_admin(security.hash_password("admin-pass"))
    atok = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"}).json()["token"]
    HA = {"Authorization": f"Bearer {atok}"}
    assert client.post("/api/upload", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}, headers=HA).status_code == 400
    resp = client.delete("/api/documents/%E4%B8%8D%E5%AD%98%E5%9C%A8", headers=HA)
    assert resp.status_code == 200 and resp.json()["deleted_chunks"] == 0


# ---------- 存量迁移 + 隔离（HTTP 层） ----------

def test_first_user_claims_legacy_data(client):
    # 预置无主错题/成绩（user_id=0）
    qid = store.cache_question("scope-legacy", {
        "qtype": "single", "topic": "压疮分期", "source": "x", "page": 1,
        "question": "旧数据题？", "options": ["A. a", "B. b", "C. c", "D. d"],
        "answer": ["A"], "explanation": "教材", "confidence": 0.8,
    })
    from app.exam.grader import grade
    grade([{"id": qid, "answer": ["A"], "explanation": "x"}], [["B"]], user_id=0)

    r = _register(client, username="mama", password="abc12345")
    assert r.json()["is_first"] is True
    assert r.json()["migrated"]["wrong_book"] >= 1

    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    wrongs = client.get("/api/exam/wrong-book", headers=h).json()
    assert any(w["id"] == qid for w in wrongs["questions"])


def test_exam_api_requires_auth_and_isolates(client):
    # 未登录访问考试接口 → 401
    assert client.get("/api/exam/stats").status_code == 401
    assert client.get("/api/exam/wrong-book").status_code == 401
    assert client.post("/api/exam/generate", json={"count": 1}).status_code == 401

    r1 = _register(client, username="mama", password="abc12345", display_name="妈妈")
    r2 = _register(client, username="xiaoming", password="abc12345", display_name="小明")
    h1 = {"Authorization": f"Bearer {r1.json()['token']}"}
    h2 = {"Authorization": f"Bearer {r2.json()['token']}"}

    # 出题（缓存命中路径，不调 LLM 也能测鉴权连通性：先塞一道缓存题）
    qid = store.cache_question("scope-auth", {
        "qtype": "single", "topic": "造口用品", "source": "y", "page": 2,
        "question": "鉴权隔离题？", "options": ["A. a", "B. b", "C. c", "D. d"],
        "answer": ["A"], "explanation": "教材", "confidence": 0.9,
    })
    from app.exam.grader import grade
    # 妈妈答错入错题本
    r = client.post("/api/exam/submit", json={
        "questions": [{"id": qid, "answer": ["A"], "explanation": "x"}],
        "answers": [["B"]],
        "mode": "practice",
    }, headers=h1)
    assert r.status_code == 200

    w1 = client.get("/api/exam/wrong-book", headers=h1).json()
    w2 = client.get("/api/exam/wrong-book", headers=h2).json()
    assert w1["total"] >= 1 and w2["total"] == 0   # 隔离生效

    stats2 = client.get("/api/exam/stats", headers=h2).json()
    assert stats2["total_answered"] == 0