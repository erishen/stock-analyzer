"""ML 模型包：LightGBM 排名 / Isolation Forest 异常检测 / K-Means 聚类 / GARCH 波动率。

安装 ML 依赖: uv sync --extra ml
"""

from .anomaly import IsolationForestDetector, compute_anomaly_report
from .clustering import KMeansClusterer, compute_cluster_report
from .common import (
    ANOMALY_FEATURES,
    CLUSTER_FEATURES,
    GBM_FEATURES,
    RANK_FEATURES,
    add_cross_sectional_ranks,
    add_target_rank,
    compute_forward_return,
    daily_rankic,
    filter_universe,
    is_st,
    latest_date,
    load_analysis_data,
    load_latest_cross_section,
    load_names,
    report_path,
    require_ml,
    resolve_stock_code,
    save_json_report,
)
from .gbm_rank import DEFAULT_PARAMS, GBMRankModel, backtest_topn, equal_weight_baseline, evaluate_deciles
from .volatility import GARCHVolatility, compute_garch_report, load_stock_returns

__all__ = [
    "ANOMALY_FEATURES",
    "CLUSTER_FEATURES",
    "DEFAULT_PARAMS",
    "GBM_FEATURES",
    "RANK_FEATURES",
    "GARCHVolatility",
    "GBMRankModel",
    "IsolationForestDetector",
    "KMeansClusterer",
    "add_cross_sectional_ranks",
    "add_target_rank",
    "backtest_topn",
    "compute_anomaly_report",
    "compute_cluster_report",
    "compute_forward_return",
    "compute_garch_report",
    "daily_rankic",
    "equal_weight_baseline",
    "evaluate_deciles",
    "filter_universe",
    "is_st",
    "latest_date",
    "load_analysis_data",
    "load_latest_cross_section",
    "load_names",
    "load_stock_returns",
    "report_path",
    "require_ml",
    "resolve_stock_code",
    "save_json_report",
]
