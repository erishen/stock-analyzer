"""Asset Snapshot 本地读取模块。

提供自定义规则选股 (src/scanner/screener) 依赖的纯本地读能力:
  - ASSET_FIELDS: 资产字段 -> 中文标签 (供前端下拉与展示)
  - load_snapshot: 读取 data/asset_snapshot.db 返回全市场市值/股本/估值快照

注意: 数据抓取/落盘逻辑 (东财/腾讯) 已迁至 data_tools/asset_fetch.py ——
     该目录不随仓库分发 (见 .gitignore)。本模块只读本地快照库, 不触碰任何外部接口。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# 资产字段 -> 中文标签 (供前端下拉与展示)
ASSET_FIELDS: dict[str, str] = {
    "close": "最新价",
    "change_percent": "涨跌幅%",
    "volume": "成交量(手)",
    "amount": "成交额(元)",
    "volume_ratio": "量比",
    "turnover_rate": "换手率%",
    "total_market_value": "总市值(亿)",
    "float_market_value": "流通市值(亿)",
    "total_shares": "总股本(亿股)",
    "float_shares": "流通股本(亿股)",
    "pe": "市盈率(动态)",
    "pb": "市净率",
}

# 资产 DB 表名
_ASSET_TABLE = "asset_snapshot"


def _db_path() -> Path:
    from config import DATA_DIR

    return DATA_DIR / "asset_snapshot.db"


def load_snapshot() -> dict:
    """读取资产快照。返回 {updated_at, items:[{code,name,...}]} 或空。"""
    db = _db_path()
    if not db.exists():
        return {"updated_at": "", "items": []}
    try:
        with sqlite3.connect(db) as conn:
            cur = conn.execute(f"SELECT * FROM {_ASSET_TABLE} ORDER BY total_market_value DESC")
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            updated = ""
            if rows:
                updated = rows[0][cols.index("updated_at")]
            items = [dict(zip(cols, r, strict=True)) for r in rows]
            # 去掉 updated_at 避免冗余
            for it in items:
                it.pop("updated_at", None)
    except sqlite3.Error as e:  # pragma: no cover
        logger.warning("读取资产快照失败: %s", e)
        return {"updated_at": "", "items": []}
    return {"updated_at": updated, "items": items}
