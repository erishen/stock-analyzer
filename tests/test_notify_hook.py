"""src/web/notify_hook.py: 公开仓库无 data_tools 时静默降级, 有则转发推送。

notify_hook 按文件路径动态加载同仓 data_tools/notify.py。公开部署没有该文件,
本测试用 monkeypatch 替换 _NOTIFY_PATH 覆盖「缺失 / 加载出错 / 正常转发」三种路径。
"""

import pytest

from web import notify_hook


@pytest.fixture(autouse=True)
def _reset_hook():
    """每个用例前后清空模块级缓存, 避免跨用例串味。"""
    notify_hook._loaded = False
    notify_hook._module = None
    yield
    notify_hook._loaded = False
    notify_hook._module = None


def test_missing_module_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(notify_hook, "_NOTIFY_PATH", tmp_path / "nope.py")
    assert notify_hook.configured() is False
    ok, msg = notify_hook.send_markdown("hi")
    assert ok is False
    assert "不可用" in msg


def test_tolerates_load_error(tmp_path, monkeypatch):
    bad = tmp_path / "notify.py"
    bad.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.setattr(notify_hook, "_NOTIFY_PATH", bad)
    assert notify_hook.configured() is False
    ok, _msg = notify_hook.send_markdown("hi")
    assert ok is False


def test_delegates_when_present(tmp_path, monkeypatch):
    fake = tmp_path / "notify.py"
    fake.write_text(
        "def configured():\n"
        "    return True\n\n"
        "def send_markdown(text, title='x', timeout=15.0):\n"
        "    return True, f'sent:{title}:{text}'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(notify_hook, "_NOTIFY_PATH", fake)
    assert notify_hook.configured() is True
    ok, msg = notify_hook.send_markdown("hello", title="T")
    assert ok is True
    assert msg == "sent:T:hello"


def test_send_markdown_swallows_exceptions(tmp_path, monkeypatch):
    boom = tmp_path / "notify.py"
    boom.write_text(
        "def configured():\n"
        "    return True\n\n"
        "def send_markdown(text, title='x', timeout=15.0):\n"
        "    raise ValueError('nope')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(notify_hook, "_NOTIFY_PATH", boom)
    ok, msg = notify_hook.send_markdown("hi")
    assert ok is False
    assert "异常" in msg
