"""Mock 工具"""

import json
from typing import Any
from unittest.mock import Mock


def mock_response(
    data: Any,
    status_code: int = 200,
    headers: dict | None = None,
) -> Mock:
    """
    创建 Mock HTTP 响应

    Args:
        data: 响应数据
        status_code: 状态码
        headers: 响应头

    Returns:
        Mock 响应对象
    """
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
    response.headers = headers or {}
    response.ok = 200 <= status_code < 300
    return response


def create_mock_db_session():
    """
    创建 Mock 数据库会话
    """
    session = Mock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


def create_mock_cache():
    """
    创建 Mock 缓存
    """
    cache = {}
    mock_cache = Mock()
    mock_cache.get = lambda key: cache.get(key)
    mock_cache.set = lambda key, value, ttl=None: cache.update({key: value})
    mock_cache.delete = lambda key: cache.pop(key, None)
    mock_cache.exists = lambda key: key in cache
    mock_cache.clear = lambda: cache.clear()
    return mock_cache
