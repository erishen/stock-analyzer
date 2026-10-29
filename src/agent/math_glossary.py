"""指标数学词典: 技术指标背后的数学定义 + 人话解释 + 信号判读。

供 AI 选股/诊断时注入给 LLM(见 schema.describe_schema 的「指标数学速查」段),
让回答不只报数字, 还能讲清「指标到底在算什么、怎么解读」——
讲解风格借鉴 work/knowledge/math 项目(先给定义, 再说直觉, 最后给判读)。
"""

from __future__ import annotations

# 完整词典: 覆盖 stock_analysis 表的全部指标列(51 个)。
# 每项三要素:
#   formula: 数学定义(可复现的公式, 供严谨回答引用)
#   meaning: 直观的人话含义(给用户解释)
#   signal : 常见信号判读(选股/诊断时的解读)
INDICATOR_MATH: dict[str, dict[str, str]] = {
    "ma5": {
        "formula": "MA5 = (C₁+C₂+…+C₅)/5, 最近 5 个交易日收盘价的算术平均",
        "meaning": "把最近 5 天的价格抹平, 代表短期平均成本线",
        "signal": "收盘价站上 MA5(close_ma5_ratio>1) 表示短期多头占优; 跌破则短期转弱",
    },
    "ma10": {
        "formula": "MA10 = 最近 10 个交易日收盘价的算术平均",
        "meaning": "短中期平均成本线, 比 MA5 平滑、滞后略大",
        "signal": "MA10 向上且价在其上: 短中期趋势偏多; 价跌破 MA10 常视为短线回调信号",
    },
    "ma20": {
        "formula": "MA20 = 最近 20 个交易日收盘价的算术平均",
        "meaning": "约一个月交易周期的平均成本, 中期趋势的分水岭",
        "signal": "close_ma20_ratio>1 站上 20 日线视为中期偏多; MA20 方向是中期趋势的最简判断",
    },
    "ma60": {
        "formula": "MA60 = 最近 60 个交易日收盘价的算术平均",
        "meaning": "约一个季度的平均成本, 长期趋势线",
        "signal": "价格在 MA60 上方且 MA60 走平/向上: 长期结构健康; 长期均线下方多为弱势区",
    },
    "close_ma5_ratio": {
        "formula": "close_ma5_ratio = 收盘价 / MA5",
        "meaning": "当前价格相对 5 日均线的位置, >1 表示站在均线上方",
        "signal": ">1.03 短线乖离偏大(可能回踩); <0.97 短线超跌(可能反弹)",
    },
    "close_ma20_ratio": {
        "formula": "close_ma20_ratio = 收盘价 / MA20",
        "meaning": "价格相对 20 日均线的位置",
        "signal": ">1 站上中期均线偏多; 明显大于 1 注意乖离风险",
    },
    "close_ma60_ratio": {
        "formula": "close_ma60_ratio = 收盘价 / MA60",
        "meaning": "价格相对 60 日均线的位置",
        "signal": "长期均线上方运行是趋势股的共同特征",
    },
    "ema12": {
        "formula": "EMA12: EMA_t = α·C_t + (1-α)·EMA_{t-1}, α = 2/(12+1) ≈ 0.1538",
        "meaning": "指数移动平均, 越近的价格权重越大, 比 MA 更快反应价格变化",
        "signal": "EMA12 上穿 EMA26 是 MACD 金叉的原始形态",
    },
    "ema26": {
        "formula": "EMA26: α = 2/(26+1) ≈ 0.0741",
        "meaning": "慢速指数均线, 代表中期成本",
        "signal": "作为 MACD 慢线的基础, 与 EMA12 的差是 DIF",
    },
    "macd": {
        "formula": "MACD(DIF) = EMA12 − EMA26",
        "meaning": "快慢指数均线的差值: 为正说明短期成本高于中期(多头动能)",
        "signal": "DIF>0 且上行: 多头动能增强; DIF<0: 空头区",
    },
    "macd_signal": {
        "formula": "DEA = EMA9(DIF), DIF 的 9 日指数均线",
        "meaning": "DIF 的平滑线, 过滤 DIF 的抖动",
        "signal": "DIF 与 DEA 的相对位置构成金叉/死叉基础",
    },
    "macd_hist": {
        "formula": "柱 = 2 × (DIF − DEA)",
        "meaning": "快慢差值的差值: 红柱=多头动能扩张, 绿柱=空头动能",
        "signal": "红柱缩短=动能衰减(警惕见顶); 绿柱缩短=动能修复(可能见底)",
    },
    "macd_cross": {
        "formula": "1=DIF 上穿 DEA(金叉), −1=DIF 下穿 DEA(死叉), 0=无交叉",
        "meaning": "把 DIF/DEA 的位置关系变成离散事件",
        "signal": "零轴上方金叉=强势启动; 零轴下方金叉=超跌反弹, 需配合量能确认",
    },
    "rsi": {
        "formula": "RSI = 100 − 100/(1+RS), RS = N 日内平均上涨幅度 / 平均下跌幅度(常用 N=14)",
        "meaning": "衡量最近涨跌力量的比值, 永远落在 0~100",
        "signal": ">70 超买(短线回调概率大); <30 超卖(超跌反弹概率大); 50 附近为多空均衡",
    },
    "rsi_overbought": {
        "formula": "标记量: 1 表示 RSI≥70, 0 表示未超买",
        "meaning": "把 RSI 超买变成可筛选的布尔字段",
        "signal": "超买+放量滞涨 是短线见顶的高风险组合",
    },
    "rsi_oversold": {
        "formula": "标记量: 1 表示 RSI≤30, 0 表示未超卖",
        "meaning": "RSI 超卖布尔化",
        "signal": "超卖+缩量企稳 常见于短线底部区域",
    },
    "boll_mid": {
        "formula": "BOLL 中轨 = MA20(收盘价)",
        "meaning": "布林带的中线, 就是 20 日均线",
        "signal": "价格围绕中轨上下波动, 中轨方向代表中期趋势",
    },
    "boll_std": {
        "formula": "σ = 最近 20 日收盘价的标准差",
        "meaning": "价格波动的统计尺度, 衡量近期波动幅度",
        "signal": "σ 收窄=波动率收缩(变盘前兆); 放大=波动加剧",
    },
    "boll_upper": {
        "formula": "上轨 = MA20 + 2σ",
        "meaning": "价格正常波动区间的上沿(统计上约 95% 的观测在其下方)",
        "signal": "触及/突破上轨: 强势但短线乖离大; 常态下价格会回归带内",
    },
    "boll_lower": {
        "formula": "下轨 = MA20 − 2σ",
        "meaning": "正常波动区间的下沿",
        "signal": "触及下轨+基本面未恶化: 统计意义上的超跌区域",
    },
    "boll_width": {
        "formula": "带宽 = (上轨−下轨)/中轨(或 4σ/中轨)",
        "meaning": "波动区间的相对宽度",
        "signal": "带宽极窄(BOLL 收口)=波动率压缩, 常伴随方向性突破",
    },
    "boll_position": {
        "formula": "位置 = (收盘价−下轨)/(上轨−下轨), 取值 0~1",
        "meaning": "收盘价在布林带内的相对位置",
        "signal": ">0.8 接近上轨(强势); <0.2 接近下轨(弱势/超跌)",
    },
    "kdj_rsv": {
        "formula": "RSV = (C − L9)/(H9 − L9) × 100, 其中 H9/L9 为最近 9 日最高/最低价",
        "meaning": "当前收盘价在最近 9 日价格区间中的相对位置",
        "signal": "RSV 是 KDJ 的原始输入, 接近 100=接近区间顶, 接近 0=接近区间底",
    },
    "kdj_k": {
        "formula": "K = 2/3·K′ + 1/3·RSV(初始 K=50)",
        "meaning": "RSV 的平滑值, 追踪价格在区间内的动量",
        "signal": "K>80 超买区, K<20 超卖区",
    },
    "kdj_d": {
        "formula": "D = 2/3·D′ + 1/3·K",
        "meaning": "K 的再平滑, 比 K 更慢",
        "signal": "K 上穿 D=金叉(买入信号候选); K 下穿 D=死叉",
    },
    "kdj_j": {
        "formula": "J = 3K − 2D",
        "meaning": "K/D 差距的放大, 对拐点更敏感, 可超出 0~100",
        "signal": "J>100 极度超买; J<0 极度超卖; J 的背离常先于 K/D 出现",
    },
    "kdj_cross": {
        "formula": "1=K 上穿 D, −1=K 下穿 D, 0=无",
        "meaning": "KDJ 金叉/死叉事件化",
        "signal": "低位(30 以下)金叉可信度高于高位金叉",
    },
    "atr": {
        "formula": "ATR = TR 的 N 日平均(常用 N=14); TR = max(H−L, |H−C′|, |L−C′|)",
        "meaning": "真实波幅: 综合当日振幅与跳空, 衡量价格真实的波动尺度",
        "signal": "ATR 大=波动大(风险高/机会大); ATR 萎缩=波动收缩",
    },
    "atr_ratio": {
        "formula": "ATR_ratio = ATR / 收盘价 × 100%",
        "meaning": "波动幅度占价格的百分比, 可跨股票比较波动性",
        "signal": "高波动股(>5%)止损位要放宽; 低波动股(<2%)适合稳健策略",
    },
    "obv": {
        "formula": "OBV_t = OBV_{t−1} + volume(收盘涨) / −volume(收盘跌)",
        "meaning": "能量潮: 把量能按涨跌方向累加, 观察资金是流入还是流出",
        "signal": "价格新高而 OBV 未新高=量价背离(上涨动能存疑); OBV 持续上行=资金在进场",
    },
    "obv_ma10": {
        "formula": "OBV 的 10 日均值",
        "meaning": "OBV 的趋势线, 过滤单日量能抖动",
        "signal": "OBV 站上其 MA10 且上行: 量能趋势健康",
    },
    "obv_signal": {
        "formula": "1=OBV 上穿 MA10, −1=下穿, 0=无",
        "meaning": "量能趋势的事件化",
        "signal": "OBV 金叉确认价格突破更可靠(量在价先)",
    },
    "williams_r": {
        "formula": "W%R = (H_n − C)/(H_n − L_n) × (−100), n 常用 14",
        "meaning": "威廉指标: 收盘价距最近 N 日高点的远近, 取值 −100~0",
        "signal": ">−20 超买; <−80 超卖",
    },
    "momentum_5d": {
        "formula": "Momentum5 = (C_t/C_{t−5} − 1) × 100%",
        "meaning": "5 日涨跌幅, 衡量短期动量",
        "signal": "连续多期为正=趋势动量在累积; 转负=短期动能衰竭",
    },
    "momentum_10d": {
        "formula": "Momentum10 = (C_t/C_{t−10} − 1) × 100%",
        "meaning": "10 日涨跌幅",
        "signal": "10 日动量是中期趋势强弱的常用代理",
    },
    "momentum_20d": {
        "formula": "Momentum20 = (C_t/C_{t−20} − 1) × 100%",
        "meaning": "20 日涨跌幅(约一个月)",
        "signal": "动量策略的核心输入: 强者恒强(趋势)与均值回归(反转)在此分歧",
    },
    "roc_10": {
        "formula": "ROC10 = (C_t − C_{t−10})/C_{t−10} × 100%",
        "meaning": "10 日变动率, 与 momentum_10d 等价的不同实现",
        "signal": "ROC 上穿 0=由跌转涨; 下穿 0=由涨转跌",
    },
    "roc_20": {
        "formula": "ROC20 = (C_t − C_{t−20})/C_{t−20} × 100%",
        "meaning": "20 日变动率",
        "signal": "20 日 ROC 的方向与 MA20 方向互为印证",
    },
    "volatility_5d": {
        "formula": "σ5 = 最近 5 日对数收益率的标准差",
        "meaning": "短期波动率: 价格短期的不确定程度",
        "signal": "波动率骤升=事件驱动/恐慌或利好; 骤降=横盘",
    },
    "volatility_20d": {
        "formula": "σ20 = 最近 20 日对数收益率的标准差",
        "meaning": "月波动率, 风险度量的标准口径",
        "signal": "年化后可对比个股风险; 高波动+高动量=进攻, 低波动=防御",
    },
    "volatility_ratio": {
        "formula": "波动率比值 = 短期波动率 / 长期波动率",
        "meaning": "波动率是放大还是收缩",
        "signal": ">1.5 波动率扩张(变盘进行中); <0.7 收缩(蓄势)",
    },
    "high_low_ratio": {
        "formula": "H/L 比 = 当日最高价 / 当日最低价",
        "meaning": "当日振幅的相对度量(不含昨收的跳空)",
        "signal": "比值大=日内多空争夺激烈",
    },
    "close_open_ratio": {
        "formula": "C/O 比 = 收盘价 / 开盘价",
        "meaning": "当日多空最终胜负: >1 收阳, <1 收阴",
        "signal": "连续收阳(C/O>1)且放量=多头掌控",
    },
    "upper_shadow": {
        "formula": "上影线 = 最高价 − max(开盘价, 收盘价)",
        "meaning": "盘中冲高后被打回来的幅度",
        "signal": "长上影(相对实体)=上方抛压重, 冲高回落警示",
    },
    "lower_shadow": {
        "formula": "下影线 = min(开盘价, 收盘价) − 最低价",
        "meaning": "盘中下探后被拉回的幅度",
        "signal": "长下影=下方承接强, 探底回升(锤头线)",
    },
    "body_size": {
        "formula": "实体 = |收盘价 − 开盘价|",
        "meaning": "K 线实体长度, 多空一方主导的程度",
        "signal": "大实体阳线=多头强势; 大实体阴线=空头强势; 十字星(实体≈0)=方向待定",
    },
    "amplitude": {
        "formula": "振幅 = (最高价 − 最低价) / 昨收 × 100%",
        "meaning": "当日价格波动范围占昨收的百分比",
        "signal": "高振幅+放量: 分歧加大; 低振幅+缩量: 观望",
    },
    "turnover_rate": {
        "formula": "换手率 = 当日成交量 / 流通股本 × 100%",
        "meaning": "当天有多少比例的流通筹码被换手",
        "signal": "换手骤升=资金活跃(可能是启动或出货); 持续高换手+滞涨=警惕派发",
    },
    "change_percent": {
        "formula": "涨跌幅 = (收盘价 − 昨收)/昨收 × 100%",
        "meaning": "单日价格变化百分比",
        "signal": "核心行情字段, 与量能、技术位置结合解读",
    },
    "pct_change": {
        "formula": "区间涨跌幅 = (期末收盘 − 期初收盘)/期初收盘 × 100%",
        "meaning": "一段区间(查询窗口)的累计涨跌",
        "signal": "用于对比区间强弱, 与 momentum 系列同族",
    },
}

# schema 注入用: 核心子集(覆盖 Agent 最常查询/解释的指标), 控制注入 token 量
SCHEMA_GLOSSARY_KEYS: list[str] = [
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "close_ma20_ratio",
    "ema12",
    "ema26",
    "macd",
    "macd_signal",
    "macd_hist",
    "macd_cross",
    "rsi",
    "rsi_overbought",
    "rsi_oversold",
    "boll_upper",
    "boll_lower",
    "boll_position",
    "boll_width",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "kdj_cross",
    "atr",
    "atr_ratio",
    "obv",
    "obv_signal",
    "williams_r",
    "momentum_5d",
    "momentum_10d",
    "momentum_20d",
    "roc_10",
    "roc_20",
    "volatility_5d",
    "volatility_20d",
    "volatility_ratio",
    "amplitude",
    "turnover_rate",
    "change_percent",
    "body_size",
]


def glossary_text(keys: list[str] | None = None) -> str:
    """渲染「指标数学速查」文本段, 供 schema_text 注入。

    每行: 指标: 数学定义 | 人话: … | 判读: …
    """
    keys = keys or SCHEMA_GLOSSARY_KEYS
    lines: list[str] = []
    for k in keys:
        item = INDICATOR_MATH.get(k)
        if not item:
            continue
        lines.append(f"- {k}: {item['formula']}；人话: {item['meaning']}；判读: {item['signal']}")
    return "\n".join(lines)
