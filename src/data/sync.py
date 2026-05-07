"""
Data Sync Module for Stock Analyzer.
数据同步模块 - 配置外部数据库路径
"""

import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_asset_lens_db_path


def sync_from_external_db(
    source_path: Path | str | None = None,
    target_path: Path | str | None = None,
    backup: bool = True,
) -> dict:
    """
    配置外部数据库路径

    当 ASSET_LENS_DB_PATH 配置后，stock-analyzer 将直接读取 asset-lens 的数据库，
    不再需要复制文件。

    Args:
        source_path: 源数据库路径，如未指定则从环境变量 ASSET_LENS_DB_PATH 获取
        target_path: 目标数据库路径（已弃用，保留兼容）
        backup: 是否备份（已弃用，保留兼容）

    Returns:
        配置结果
    """
    if source_path is None:
        source_path = os.environ.get("ASSET_LENS_DB_PATH")

    source = Path(source_path) if source_path else get_asset_lens_db_path()

    result = {
        "source": str(source),
        "success": False,
        "source_size": 0,
        "message": "",
    }

    if not source.exists():
        result["message"] = f"源数据库不存在: {source}"
        return result

    result["source_size"] = source.stat().st_size
    result["success"] = True
    result["message"] = f"数据路径已配置: {source}"
    return result


def get_db_info(source_path: Path | str | None = None) -> dict:
    """
    获取数据库信息

    Args:
        source_path: 数据库路径

    Returns:
        数据库信息
    """
    import sqlite3

    if source_path is None:
        source_path = os.environ.get("ASSET_LENS_DB_PATH")

    source = Path(source_path) if source_path else get_asset_lens_db_path()

    info = {
        "path": str(source),
        "exists": False,
        "size": 0,
        "tables": [],
        "stock_count": 0,
        "kline_count": 0,
        "last_update": None,
    }

    if not source.exists():
        return info

    info["exists"] = True
    info["size"] = source.stat().st_size

    try:
        with sqlite3.connect(str(source)) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            info["tables"] = [row[0] for row in cursor.fetchall()]

            if "stock_klines" in info["tables"]:
                cursor = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_klines")
                info["stock_count"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM stock_klines")
                info["kline_count"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT MAX(date) FROM stock_klines")
                info["last_update"] = cursor.fetchone()[0]
    except Exception:
        pass

    return info


def run_sync(backup: bool = True, source_path: str | Path | None = None) -> dict:
    """
    运行数据路径配置

    Args:
        backup: 已弃用，保留兼容
        source_path: 源数据库路径

    Returns:
        配置结果
    """
    print("\n" + "=" * 60)
    print("🔄 数据路径配置")
    print("=" * 60)

    info = get_db_info(source_path)

    if not info["exists"]:
        print(f"\n❌ 数据库不存在: {info['path']}")
        print("\n请在 .env 文件中配置 ASSET_LENS_DB_PATH 指向 asset-lens 的数据库:")
        print("  ASSET_LENS_DB_PATH=../investkit_utils/data/asset_lens.db")
        return {"success": False, "message": "数据库不存在"}

    print(f"\n📁 数据库路径: {info['path']}")
    print(f"   文件大小: {info['size'] / 1024 / 1024:.2f} MB")
    print(f"   股票数量: {info['stock_count']:,}")
    print(f"   K线数量: {info['kline_count']:,}")
    print(f"   最后更新: {info['last_update']}")
    print("\n✅ 数据路径已配置，stock-analyzer 将直接读取此数据库")

    return {"success": True, "message": f"数据路径已配置: {info['path']}"}
