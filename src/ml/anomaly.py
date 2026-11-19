"""Isolation Forest 异常检测：识别指标画像异常的全市场个股。

方法:
  - 样本: 某交易日全市场横截面, 特征为技术指标(横截面排名归一化, 消除量纲/市场状态)
  - 模型: sklearn IsolationForest (默认 contamination 取全市场尾部 ~1%)
  - 输出: 每只股票的异常分数 + 判定标签 + 偏离方向, 按异常程度排序

用途: 捕捉放量异动 / 极端波动 / 指标画像脱离群体的个股, 作为信号扫描的补充视角。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.common import (
    ANOMALY_FEATURES,
    add_cross_sectional_ranks,
    latest_date,
    load_latest_cross_section,
    report_path,
    require_ml,
    save_json_report,
)


class IsolationForestDetector:
    """Isolation Forest 异常检测器。"""

    def __init__(
        self,
        features: list[str] | None = None,
        contamination: float = 0.01,
        n_estimators: int = 200,
        random_state: int = 42,
    ):
        self.features = list(features or ANOMALY_FEATURES)
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model = None
        self._is_fitted = False

    def _feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """特征矩阵（含缺失填充），按日做横截面排名归一化以消除量纲/市场状态。"""
        if "date" in df.columns and not df.empty:
            x = add_cross_sectional_ranks(df, self.features)[self.features]
        else:
            x = df[self.features].copy()
        return x.astype("float64").fillna(0.5).to_numpy()

    def fit_predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """拟合并返回 (labels, anomaly_scores)。labels: -1=异常, 1=正常 (sklearn 约定)。"""
        require_ml("sklearn")
        from sklearn.ensemble import IsolationForest

        x = self._feature_matrix(df)
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(x)
        labels = self.model.predict(x)
        scores = self.model.score_samples(x)  # 越低越异常
        self._is_fitted = True
        return labels, scores

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """返回带 label / anomaly_score / severity 的 DataFrame（异常在前）。"""
        if df.empty:
            return pd.DataFrame()
        labels, scores = self.fit_predict(df)
        out = df.copy()
        out["label"] = labels
        out["anomaly_score"] = scores
        # 归一化到 0~100, 越高越异常
        lo, hi = float(np.min(scores)), float(np.max(scores))
        out["severity"] = 100.0 * (1.0 - (scores - lo) / (hi - lo)) if hi > lo else 0.0
        out = out.sort_values("anomaly_score").reset_index(drop=True)
        return out


def compute_anomaly_report(
    date: str | None = None,
    db_path: str | None = None,
    contamination: float = 0.01,
    n_estimators: int = 200,
    top_n: int = 20,
    random_state: int = 42,
) -> dict:
    """对指定日期全市场做 Isolation Forest 异常检测, 返回报告 dict（不落盘）。

    供 CLI (run_anomaly) 与 Web (/api/ml/anomaly) 复用。无数据时抛 ValueError。
    """
    require_ml("sklearn")  # 前置校验, 给出可读报错
    date = date or latest_date(db_path)
    if not date:
        raise ValueError("未找到分析库数据，请先运行 ETL (make etl)")

    df = load_latest_cross_section(ANOMALY_FEATURES, date, db_path)
    detector = IsolationForestDetector(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
    )
    result = detector.detect(df)
    anomalies = result[result["label"] == -1]

    top = anomalies.head(top_n)
    rows = []
    for _, r in top.iterrows():
        rows.append(
            {
                "code": r["code"],
                "name": r["name"],
                "severity": round(float(r["severity"]), 1),
                "anomaly_score": round(float(r["anomaly_score"]), 4),
                "change_percent": round(float(r.get("change_percent", np.nan)), 2),
                "amplitude": round(float(r.get("amplitude", np.nan)), 2),
                "turnover_rate": round(float(r.get("turnover_rate", np.nan)), 2),
            }
        )

    return {
        "model": "isolation_forest",
        "success": True,
        "date": date,
        "total_stocks": len(df),
        "n_anomalies": len(anomalies),
        "contamination": contamination,
        "top_anomalies": rows,
    }


def run_anomaly(args) -> None:
    """CLI 入口：对最新交易日全市场做 Isolation Forest 异常检测。"""
    try:
        report = compute_anomaly_report(
            date=args.date,
            db_path=args.db,
            contamination=args.contamination,
            n_estimators=args.n_estimators,
            top_n=args.top_n,
            random_state=args.random_state,
        )
    except ValueError as e:
        raise SystemExit(str(e)) from e
    out = report_path(args.output, "ml_anomaly_report.json")
    save_json_report(report, out)
    print(f"  异常股: {report['n_anomalies']} / {report['total_stocks']}")
    print("\nTop 异常:")
    for r in report["top_anomalies"]:
        print(f"  {r['name']:<8} {r['code']}  异常度 {r['severity']:>5.1f}  涨跌 {r['change_percent']:>+6.2f}%")
