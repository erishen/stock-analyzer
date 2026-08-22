"""把模拟仓当前持仓组装成给 Agent 看的中文快照文本。

复用 paper_trading 的持仓诊断结果, 让 Agent 在回答「持仓/我的股票」类问题时
站在真实的持仓与现价盈亏之上给出建议, 而不必凭空猜测。
"""

from __future__ import annotations


def build_paper_context(db_path) -> str:
    """返回持仓快照文本。无持仓或异常时返回空串。"""
    try:
        from ..web.paper_trading import get_paper
    except Exception:  # 模块未就绪时静默降级
        return ""

    try:
        pf = get_paper(db_path)
        diag = pf.get_diagnosis()
    except Exception:
        return ""

    if not diag.get("success"):
        return ""

    summary = diag.get("summary", {})
    lines = [
        f"持仓 {summary.get('position_count', 0)} 只, 单票最大仓位占比 {summary.get('max_weight', 0)}%, "
        f"总盈亏率 {summary.get('total_pnl_pct', 0)}%。",
    ]
    for pos in diag.get("positions", []):
        weight = pos.get("weight")
        weight_txt = f", 仓位占比{weight}%" if weight not in (None, 0, "", "0") else ""
        # 隐私脱敏: 只外发持仓代码、名称、盈亏率与建议; 不下发精确成本/现价/市值金额
        lines.append(
            f"- {pos.get('name')}({pos.get('code')}): 盈亏{pos.get('pnl_pct')}%{weight_txt}, "
            f"建议: {pos.get('advice')}"
        )
    market = diag.get("market", {}) or {}
    lines.append(f"大盘环境: {market.get('state', '未知')} · {market.get('advice', '')}")
    return "\n".join(lines)
