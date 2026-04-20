"""
Data Sync Module for Stock Analyzer.
数据同步模块 - 从外部数据库同步
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def sync_from_external_db(
    source_path: Path | str | None = None,
    target_path: Path | str | None = None,
    backup: bool = True,
) -> dict:
    """
    从外部数据库同步

    Args:
        source_path: 源数据库路径，如未指定则从环境变量 SYNC_DB_SOURCE 获取
        target_path: 目标数据库路径
        backup: 是否备份目标数据库

    Returns:
        同步结果
    """
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"

    if source_path is None:
        source_path = os.environ.get("SYNC_DB_SOURCE")

    default_target = data_dir / "asset_lens.db"

    source = Path(source_path) if source_path else None
    target = Path(target_path) if target_path else default_target

    result = {
        "source": str(source) if source else None,
        "target": str(target),
        "success": False,
        "backup_created": False,
        "backup_path": None,
        "source_size": 0,
        "target_size": 0,
        "message": "",
    }

    if not source:
        result["message"] = "未指定源数据库路径。请设置环境变量 SYNC_DB_SOURCE 或通过参数传入。"
        return result

    if not source.exists():
        result["message"] = f"源数据库不存在: {source}"
        return result

    result["source_size"] = source.stat().st_size

    if target.exists() and backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target.with_suffix(f".db.backup_{timestamp}")
        shutil.copy2(target, backup_path)
        result["backup_created"] = True
        result["backup_path"] = str(backup_path)
        result["target_size"] = target.stat().st_size

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        result["success"] = True
        result["target_size"] = target.stat().st_size
        result["message"] = "同步成功"
    except Exception as e:
        result["message"] = f"同步失败: {e}"

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
        source_path = os.environ.get("SYNC_DB_SOURCE")

    info = {
        "path": str(source_path) if source_path else None,
        "exists": False,
        "size": 0,
        "tables": [],
        "stock_count": 0,
        "kline_count": 0,
        "last_update": None,
    }

    if not source_path:
        return info

    source = Path(source_path)

    if not source.exists():
        return info

    info["exists"] = True
    info["size"] = source.stat().st_size

    try:
        conn = sqlite3.connect(str(source))

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        info["tables"] = [row[0] for row in cursor.fetchall()]

        if "stock_klines" in info["tables"]:
            cursor = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_klines")
            info["stock_count"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM stock_klines")
            info["kline_count"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT MAX(date) FROM stock_klines")
            info["last_update"] = cursor.fetchone()[0]

        conn.close()
    except Exception:
        pass

    return info


def run_sync(backup: bool = True, source_path: str | Path | None = None) -> dict:
    """
    运行同步的便捷函数

    Args:
        backup: 是否备份
        source_path: 源数据库路径

    Returns:
        同步结果
    """
    print("\n" + "=" * 60)
    print("🔄 数据同步")
    print("=" * 60)

    info = get_db_info(source_path)
    if not info["path"]:
        print("\n❌ 未指定源数据库路径")
        print("\n使用方法:")
        print("  1. 设置环境变量: export SYNC_DB_SOURCE=/path/to/stock_data.db")
        print("  2. 或通过命令行: python -m src.main sync --source /path/to/stock_data.db")
        return {"success": False, "message": "未指定源数据库路径"}

    if not info["exists"]:
        print(f"\n❌ 源数据库不存在: {info['path']}")
        return {"success": False, "message": "源数据库不存在"}

    print(f"\n📁 源数据库: {info['path']}")
    print(f"   文件大小: {info['size'] / 1024 / 1024:.2f} MB")
    print(f"   股票数量: {info['stock_count']:,}")
    print(f"   K线数量: {info['kline_count']:,}")
    print(f"   最后更新: {info['last_update']}")

    result = sync_from_external_db(source_path=source_path, backup=backup)

    if result["success"]:
        print("\n✅ 同步成功!")
        print(f"   目标: {result['target']}")
        if result["backup_created"]:
            print(f"   备份: {result['backup_path']}")
    else:
        print(f"\n❌ {result['message']}")

    return result
