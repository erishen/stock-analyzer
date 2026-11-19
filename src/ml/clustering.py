"""K-Means 聚类：按指标画像把全市场个股分成若干同质簇。

方法:
  - 样本: 某交易日全市场横截面, 特征为技术指标(横截面排名归一化)
  - 预处理: StandardScaler 标准化(排名归一化后接近均匀, 标准化后更适合欧氏距离)
  - 模型: sklearn KMeans (默认 6 簇, 可自动按轮廓系数选 k)
  - 输出: 每簇的指标画像均值(相对全市场 z-score) + 代表个股 + 簇规模占比

用途: 识别当前市场的风格聚集(如强势动量簇 / 超跌反弹簇 / 高波动簇), 辅助板块与风格轮动判断。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.common import (
    CLUSTER_FEATURES,
    add_cross_sectional_ranks,
    latest_date,
    load_latest_cross_section,
    report_path,
    require_ml,
    save_json_report,
)


class KMeansClusterer:
    """K-Means 股票聚类器。"""

    def __init__(
        self,
        features: list[str] | None = None,
        n_clusters: int = 6,
        random_state: int = 42,
    ):
        self.features = list(features or CLUSTER_FEATURES)
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.model = None
        self.scaler = None
        self._centroids: np.ndarray | None = None

    def _feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """按日横截面排名归一化 + 标准化。"""
        if "date" in df.columns and not df.empty:
            x = add_cross_sectional_ranks(df, self.features)[self.features]
        else:
            x = df[self.features].copy()
        return x.astype("float64").fillna(0.5).to_numpy()

    def fit_predict(self, df: pd.DataFrame) -> np.ndarray:
        """拟合聚类并返回簇标签（与 df 行序一致）。"""
        require_ml("sklearn")
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        x = self._feature_matrix(df)
        self.scaler = StandardScaler()
        xs = self.scaler.fit_transform(x)
        self.model = KMeans(n_clusters=self.n_clusters, random_state=self.random_state, n_init=10)
        labels = self.model.fit_predict(xs)
        self._centroids = self.model.cluster_centers_
        return labels

    def pick_k_by_silhouette(self, df: pd.DataFrame, k_range: range | None = None) -> tuple[int, float]:
        """按轮廓系数在 k_range 内选最优 k。返回 (best_k, silhouette)。"""
        require_ml("sklearn")
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler

        x = self._feature_matrix(df)
        xs = StandardScaler().fit_transform(x)
        best_k, best_score = self.n_clusters, -1.0
        for k in k_range or range(3, 11):
            if k >= len(df):
                continue
            km = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            labels = km.fit_predict(xs)
            try:
                s = float(silhouette_score(xs, labels))
            except ValueError:
                s = -1.0
            if s > best_score:
                best_k, best_score = k, s
        return best_k, best_score

    def describe(self, df: pd.DataFrame, labels: np.ndarray) -> list[dict]:
        """每簇画像描述：全市场 z-score + 规模 + 代表个股。"""
        out: list[dict] = []
        if self._centroids is None or self.scaler is None:
            return out
        mean = df[self.features].mean()
        std = df[self.features].std().replace(0, np.nan)
        for k in range(self.n_clusters):
            idx = np.where(labels == k)[0]
            if len(idx) == 0:
                continue
            cluster = df.iloc[idx]
            # 画像: 簇内均值相对全市场的 z-score（越正越强/越高）
            profile = {}
            for f in self.features:
                m = cluster[f].mean()
                profile[f] = round(float((m - mean[f]) / std[f]), 2) if pd.notna(std[f]) and std[f] else 0.0
            top_stocks = cluster.nlargest(3, "change_percent")[["code", "name", "change_percent"]].to_dict("records")
            out.append(
                {
                    "cluster": int(k),
                    "size": len(idx),
                    "share_pct": round(len(idx) / len(df) * 100, 2),
                    "avg_change_pct": round(float(cluster["change_percent"].mean()), 2),
                    "profile_zscore": profile,
                    "top_stocks": top_stocks,
                }
            )
        return out


def compute_cluster_report(
    k: int = 6,
    date: str | None = None,
    db_path: str | None = None,
    auto_k: bool = False,
    random_state: int = 42,
) -> dict:
    """对指定日期全市场做 K-Means 聚类, 返回报告 dict（不落盘）。

    供 CLI (run_cluster) 与 Web (/api/ml/cluster) 复用。无数据时抛 ValueError。
    """
    require_ml("sklearn")
    date = date or latest_date(db_path)
    if not date:
        raise ValueError("未找到分析库数据，请先运行 ETL (make etl)")

    df = load_latest_cross_section(CLUSTER_FEATURES, date, db_path)
    clusterer = KMeansClusterer(n_clusters=k, random_state=random_state)
    best_k, sil = k, None
    if auto_k:
        best_k, sil = clusterer.pick_k_by_silhouette(df)
        clusterer.n_clusters = best_k

    labels = clusterer.fit_predict(df)
    clusters = clusterer.describe(df, labels)

    return {
        "model": "kmeans",
        "success": True,
        "date": date,
        "n_clusters": best_k,
        "silhouette": round(sil, 3) if sil is not None else None,
        "n_stocks": len(df),
        "clusters": clusters,
    }


def run_cluster(args) -> None:
    """CLI 入口：对最新交易日全市场做 K-Means 聚类。"""
    try:
        report = compute_cluster_report(
            k=args.k,
            date=args.date,
            db_path=args.db,
            auto_k=args.auto_k,
            random_state=args.random_state,
        )
    except ValueError as e:
        raise SystemExit(str(e)) from e
    out = report_path(args.output, "ml_cluster_report.json")
    save_json_report(report, out)
    print(f"\n聚类概况 (k={report['n_clusters']}):")
    for c in report["clusters"]:
        print(f"  簇{c['cluster']}: {c['size']} 只 ({c['share_pct']}%)  均涨 {c['avg_change_pct']:+.2f}%")
