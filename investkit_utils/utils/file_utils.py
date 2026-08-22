"""文件工具"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在

    Args:
        path: 目录路径

    Returns:
        Path 对象

    示例:
        >>> ensure_dir("data/cache")
        PosixPath('data/cache')
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(file_path: str | Path, default: Any = None) -> Any:
    """读取 JSON 文件

    Args:
        file_path: 文件路径
        default: 默认值 (文件不存在时)

    Returns:
        JSON 数据

    示例:
        >>> read_json("config.json", default={})
        {"key": "value"}
    """
    path = Path(file_path)
    if not path.exists():
        return default

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(
    file_path: str | Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """写入 JSON 文件

    Args:
        file_path: 文件路径
        data: 数据
        indent: 缩进
        ensure_ascii: 是否转义非 ASCII 字符

    示例:
        >>> write_json("config.json", {"key": "value"})
    """
    path = Path(file_path)
    ensure_dir(path.parent)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)


def read_text(file_path: str | Path, default: str = "") -> str:
    """读取文本文件

    Args:
        file_path: 文件路径
        default: 默认值 (文件不存在时)

    Returns:
        文本内容

    示例:
        >>> read_text("README.md")
        "# README"
    """
    path = Path(file_path)
    if not path.exists():
        return default

    with open(path, encoding="utf-8") as f:
        return f.read()


def write_text(
    file_path: str | Path,
    content: str,
    append: bool = False,
) -> None:
    """写入文本文件

    Args:
        file_path: 文件路径
        content: 内容
        append: 是否追加

    示例:
        >>> write_text("log.txt", "Hello\\n")
    """
    path = Path(file_path)
    ensure_dir(path.parent)

    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        f.write(content)


def read_lines(file_path: str | Path) -> list[str]:
    """读取文件行

    Args:
        file_path: 文件路径

    Returns:
        行列表

    示例:
        >>> read_lines("data.csv")
        ["header", "row1", "row2"]
    """
    path = Path(file_path)
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_file_info(file_path: str | Path) -> dict[str, Any] | None:
    """获取文件信息

    Args:
        file_path: 文件路径

    Returns:
        文件信息字典

    示例:
        >>> get_file_info("data.csv")
        {"size": 1024, "modified": "2024-01-01T00:00:00", ...}
    """
    path = Path(file_path)
    if not path.exists():
        return None

    stat = path.stat()
    return {
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "size": stat.st_size,
        "size_human": format_file_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
    }


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        人类可读的大小字符串

    示例:
        >>> format_file_size(1024)
        "1.00 KB"
        >>> format_file_size(1536)
        "1.50 KB"
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def clean_dir(
    dir_path: str | Path,
    pattern: str = "*",
    keep_dir: bool = True,
) -> int:
    """清理目录

    Args:
        dir_path: 目录路径
        pattern: 文件模式
        keep_dir: 是否保留目录本身

    Returns:
        删除的文件数

    示例:
        >>> clean_dir("cache", pattern="*.tmp")
        5
    """
    path = Path(dir_path)
    if not path.exists():
        return 0

    count = 0
    for item in path.glob(pattern):
        if item.is_file():
            item.unlink()
            count += 1
        elif item.is_dir():
            shutil.rmtree(item)
            count += 1

    if not keep_dir and path.exists():
        path.rmdir()

    return count


def copy_file(
    src: str | Path,
    dst: str | Path,
    overwrite: bool = False,
) -> bool:
    """复制文件

    Args:
        src: 源文件
        dst: 目标文件
        overwrite: 是否覆盖

    Returns:
        是否成功

    示例:
        >>> copy_file("data.csv", "backup/data.csv")
        True
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        return False

    if dst_path.exists() and not overwrite:
        return False

    ensure_dir(dst_path.parent)
    shutil.copy2(src_path, dst_path)
    return True


def move_file(
    src: str | Path,
    dst: str | Path,
    overwrite: bool = False,
) -> bool:
    """移动文件

    Args:
        src: 源文件
        dst: 目标文件
        overwrite: 是否覆盖

    Returns:
        是否成功

    示例:
        >>> move_file("data.csv", "archive/data.csv")
        True
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        return False

    if dst_path.exists() and not overwrite:
        return False

    ensure_dir(dst_path.parent)
    shutil.move(str(src_path), str(dst_path))
    return True


def find_files(
    dir_path: str | Path,
    pattern: str = "*",
    recursive: bool = False,
) -> list[Path]:
    """查找文件

    Args:
        dir_path: 目录路径
        pattern: 文件模式
        recursive: 是否递归

    Returns:
        文件路径列表

    示例:
        >>> find_files("data", "*.csv")
        [PosixPath('data/file1.csv'), PosixPath('data/file2.csv')]
    """
    path = Path(dir_path)
    if not path.exists():
        return []

    if recursive:
        return list(path.rglob(pattern))
    return list(path.glob(pattern))


def get_latest_file(
    dir_path: str | Path,
    pattern: str = "*",
) -> Path | None:
    """获取最新文件

    Args:
        dir_path: 目录路径
        pattern: 文件模式

    Returns:
        最新文件路径

    示例:
        >>> get_latest_file("logs", "*.log")
        PosixPath('logs/app_20240101.log')
    """
    files = find_files(dir_path, pattern)
    if not files:
        return None

    return max(files, key=lambda f: f.stat().st_mtime)
