"""LLM 客户端: 复用 DataPulse 的 OpenAI 兼容配置, 直接调用 chat completions。

不引入额外依赖(用标准库 urllib), 支持 DeepSeek / 火山引擎 / OpenAI 等任意
OpenAI 兼容端点。配置优先取 datapulse/.env, 其次当前环境变量。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# stock-analyzer 根目录 (src/agent/llm.py -> src/agent -> src -> <root>)
_SA_ROOT = Path(__file__).resolve().parent.parent.parent
# DataPulse 项目(.env 所在)位于 invest-kit/work/harness/datapulse
_DATAPULSE_ENV = _SA_ROOT.parent.parent / "work" / "harness" / "datapulse" / ".env"

SYSTEM_PROMPT = (
    "你是一名严谨的 A股 量化数据分析师。你能读懂 SQLite 里的股票日频行情与技术指标表, "
    "用自然语言回答用户关于行情、指标、选股、持仓的问题。"
    "回答问题必须基于查询到的真实数据, 给出中文结论; 不确定时说明你的推断和局限。"
)


def _parse_env(path: Path) -> dict[str, str]:
    """极简 .env 解析 (KEY=VALUE, 忽略空行/注释/引号)。"""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:  # pragma: no cover
        logger.warning("读取 %s 失败: %s", path, e)
    return env


# 运行时覆盖配置(设置 Tab 写入), 优先于 .env
_OVERRIDE_FILE = _SA_ROOT / "data" / "llm_settings.json"


def _load_override() -> dict[str, str]:
    try:
        if _OVERRIDE_FILE.exists():
            data = json.loads(_OVERRIDE_FILE.read_text(encoding="utf-8"))
            return {k: str(v).strip() for k, v in data.items() if v}
    except Exception as e:  # pragma: no cover
        logger.warning("读取运行时 LLM 配置失败: %s", e)
    return {}


def _save_override(cfg: dict[str, str]) -> None:
    _OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def save_override(cfg: dict[str, str]) -> None:
    """保存运行时 LLM 配置覆盖(设置 Tab 使用)。"""
    clean = {k: (v or "").strip() for k, v in cfg.items()}
    _save_override(clean)


def clear_override() -> None:
    """清除运行时覆盖, 恢复使用 .env 配置。"""
    try:
        if _OVERRIDE_FILE.exists():
            _OVERRIDE_FILE.unlink()
    except Exception as e:  # pragma: no cover
        logger.warning("清除运行时 LLM 配置失败: %s", e)


def get_llm_config() -> dict[str, str]:
    """LLM 配置 (运行时覆盖 > stock-analyzer .env > datapulse .env > 环境变量)。"""
    sa_env = _parse_env(_SA_ROOT / ".env")
    dp_env = _parse_env(_DATAPULSE_ENV)
    env = {**dp_env, **sa_env}  # stock-analyzer 优先
    cfg = {
        "base_url": env.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "api_key": env.get("LLM_API_KEY", ""),
        "model": env.get("LLM_MODEL", "gpt-4o-mini"),
    }
    # 环境变量可覆盖
    if os_env := __import__("os").environ:
        cfg["base_url"] = (os_env.get("LLM_BASE_URL") or cfg["base_url"]).rstrip("/")
        cfg["api_key"] = os_env.get("LLM_API_KEY") or cfg["api_key"]
        cfg["model"] = os_env.get("LLM_MODEL") or cfg["model"]
    # 运行时覆盖优先(设置 Tab 保存的)
    override = _load_override()
    for k in ("base_url", "api_key", "model"):
        if override.get(k):
            cfg[k] = override[k].rstrip("/") if k == "base_url" else override[k]
    return cfg


def require_llm_config() -> dict[str, str]:
    cfg = get_llm_config()
    if not cfg["api_key"]:
        raise RuntimeError("未找到 LLM_API_KEY: 请在工作区 work/harness/datapulse/.env 里配置 LLM 凭证")
    return cfg


def _post(url: str, payload: dict, api_key: str, timeout: float = 90.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        logger.error("LLM HTTP %s: %s", e.code, body[:500])
        raise RuntimeError(f"LLM 服务返回错误 {e.code}: {body[:200]}") from e


def chat_raw(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """发送对话, 返回纯文本内容。"""
    cfg = require_llm_config()
    payload: dict = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    data = _post(f"{cfg['base_url']}/chat/completions", payload, cfg["api_key"])
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:  # pragma: no cover
        raise RuntimeError(f"LLM 响应异常: {data}") from e


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def chat_json(messages: list[dict], temperature: float = 0.1) -> dict:
    """发送对话并解析模型返回的 JSON 对象 (容忍 ```json 代码块包裹)。"""
    text = chat_raw(messages, temperature=temperature)
    text = text.strip()
    m = _JSON_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # 尝试从文本里提取首个 {..} 平衡块
    start, depth = -1, 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth, start = depth + 1, i if start < 0 else start
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start, depth = -1, 0
    raise ValueError(f"模型未返回有效 JSON: {text[:200]}")


def messages(system: str = SYSTEM_PROMPT) -> list[dict]:
    return [{"role": "system", "content": system}]
