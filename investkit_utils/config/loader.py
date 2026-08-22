"""InvestKit 配置加载器

支持:
- YAML 配置文件加载
- 环境变量替换 ${VAR_NAME}
- 配置继承和合并
- 多项目配置管理
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from investkit_utils.config.models import Config
from investkit_utils.utils.data_utils import deep_merge

_config_cache: dict[str, Config] = {}
_config_paths: dict[str, Path] = {}
_default_config_path: Path | None = None


class ConfigLoader:
    """配置加载器

    支持从 YAML 文件加载配置，并进行环境变量替换。

    示例:
        # 从文件加载
        config = ConfigLoader.load_from_file("config.yaml")

        # 从多个文件合并
        config = ConfigLoader.load_from_files(
            "config.base.yaml",
            "config.project.yaml"
        )

        # 环境变量替换
        # config.yaml 中使用 ${VAR_NAME} 会被环境变量替换
    """

    ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

    @classmethod
    def load_from_file(cls, path: str | Path) -> Config:
        """从 YAML 文件加载配置

        Args:
            path: 配置文件路径

        Returns:
            Config 对象
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        data = cls._substitute_env_vars(data)
        return Config(**data)

    @classmethod
    def load_from_files(cls, *paths: str | Path) -> Config:
        """从多个 YAML 文件加载并合并配置

        后面的文件会覆盖前面的配置。

        Args:
            *paths: 配置文件路径列表

        Returns:
            合并后的 Config 对象
        """
        merged_data: dict[str, Any] = {}

        for path in paths:
            path = Path(path)
            if not path.exists():
                continue

            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            merged_data = deep_merge(merged_data, data)

        merged_data = cls._substitute_env_vars(merged_data)
        return Config(**merged_data)

    @classmethod
    def load_for_project(
        cls,
        project_name: str,
        base_path: Path | None = None,
        config_dir: Path | None = None,
    ) -> Config:
        """为特定项目加载配置

        加载顺序:
        1. config.base.yaml (基础配置)
        2. config.{project_name}.yaml (项目配置)
        3. 环境变量覆盖

        Args:
            project_name: 项目名称 (如 asset-lens, lobster)
            base_path: 项目根目录
            config_dir: 配置文件目录

        Returns:
            项目配置对象
        """
        if config_dir is None:
            config_dir = Path(__file__).parent

        base_config = config_dir / "config.base.yaml"
        project_config = config_dir / f"config.{project_name}.yaml"
        local_config = base_path / "config.local.yaml" if base_path else None

        paths = [base_config, project_config]
        if local_config and local_config.exists():
            paths.append(local_config)

        return cls.load_from_files(*paths)

    @classmethod
    def _substitute_env_vars(cls, data: Any) -> Any:
        """递归替换环境变量

        将 ${VAR_NAME} 替换为实际的环境变量值。
        如果环境变量不存在，替换为空字符串。
        """
        if isinstance(data, dict):
            return {k: cls._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return cls._replace_env_var(data)
        return data

    @classmethod
    def _replace_env_var(cls, value: str) -> str:
        """替换字符串中的环境变量"""

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return cls.ENV_VAR_PATTERN.sub(replacer, value)


def get_config(project_name: str | None = None) -> Config:
    """获取配置

    如果指定了 project_name，返回该项目的配置。
    否则返回默认配置。

    Args:
        project_name: 项目名称 (可选)

    Returns:
        Config 对象
    """
    global _config_cache, _default_config_path

    cache_key = project_name or "default"

    if cache_key in _config_cache:
        return _config_cache[cache_key]

    if project_name:
        config = ConfigLoader.load_for_project(project_name)
    elif _default_config_path:
        config = ConfigLoader.load_from_file(_default_config_path)
    else:
        config = Config()

    _config_cache[cache_key] = config
    return config


def reload_config(project_name: str | None = None) -> Config:
    """重新加载配置

    清除缓存并重新加载配置。

    Args:
        project_name: 项目名称 (可选)

    Returns:
        重新加载的 Config 对象
    """
    global _config_cache

    cache_key = project_name or "default"
    _config_cache.pop(cache_key, None)

    return get_config(project_name)


def set_config_path(path: str | Path, project_name: str | None = None) -> None:
    """设置配置文件路径

    Args:
        path: 配置文件路径
        project_name: 项目名称 (可选，用于多项目配置)
    """
    global _config_paths, _default_config_path

    path = Path(path)
    if project_name:
        _config_paths[project_name] = path
    else:
        _default_config_path = path


def clear_config_cache() -> None:
    """清除所有配置缓存"""
    global _config_cache
    _config_cache = {}
