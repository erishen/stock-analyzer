"""
Sync Environment Variables from external project.
从外部项目同步环境变量
"""

import os
from pathlib import Path


def sync_env_from_external(source_path: str | Path | None = None) -> dict:
    """从外部项目同步 .env 文件

    Args:
        source_path: 源 .env 文件路径，如未指定则从环境变量 SYNC_ENV_SOURCE 获取

    Returns:
        同步结果字典
    """
    if source_path is None:
        source_path = os.environ.get("SYNC_ENV_SOURCE")

    if not source_path:
        return {
            "success": False,
            "error": "未指定源文件路径。请设置环境变量 SYNC_ENV_SOURCE 或通过参数传入。",
        }

    source_env = Path(source_path)
    target_env = Path(__file__).parent.parent.parent / ".env"

    if not source_env.exists():
        return {
            "success": False,
            "error": f"源 .env 文件不存在: {source_env}",
        }

    try:
        content = source_env.read_text(encoding="utf-8")

        target_env.write_text(content, encoding="utf-8")

        lines = [line for line in content.split("\n") if line.strip() and not line.startswith("#")]
        keys = [line.split("=")[0] for line in lines if "=" in line]

        return {
            "success": True,
            "source": str(source_env),
            "target": str(target_env),
            "keys": keys,
            "message": f"已同步 {len(keys)} 个环境变量",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def run_sync_env(source_path: str | Path | None = None) -> dict:
    """运行同步

    Args:
        source_path: 源 .env 文件路径
    """
    print("\n" + "=" * 60)
    print("🔄 同步环境变量")
    print("=" * 60)

    result = sync_env_from_external(source_path)

    if result["success"]:
        print(f"\n✅ {result['message']}")
        print(f"   源文件: {result['source']}")
        print(f"   目标文件: {result['target']}")
        print(f"   同步的 Key: {', '.join(result['keys'])}")
    else:
        print(f"\n❌ 同步失败: {result['error']}")
        print("\n使用方法:")
        print("  1. 设置环境变量: export SYNC_ENV_SOURCE=/path/to/.env")
        print("  2. 或通过命令行: python -m src.main sync-env --source /path/to/.env")

    return result


if __name__ == "__main__":
    run_sync_env()
