import { FC, useState, useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { MLAnomalyResult, MLClusterResult, MLGarchResult, MLGBMResult, MLGBMTrainTask, MLStatus } from '@/types'
import { api } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'

const fmt = (v: number | null | undefined, digits = 2): string =>
  v == null || Number.isNaN(v) ? '-' : v.toFixed(digits)

export const MLPanel: FC = () => {
  const [status, setStatus] = useState<MLStatus | null>(null)
  const [anomaly, setAnomaly] = useState<MLAnomalyResult | null>(null)
  const [cluster, setCluster] = useState<MLClusterResult | null>(null)
  const [garch, setGarch] = useState<MLGarchResult | null>(null)
  const [gbm, setGbm] = useState<MLGBMResult | null>(null)
  const [k, setK] = useState(6)
  const [code, setCode] = useState('600000')
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  // LightGBM 训练: 年份窗口 + 任务状态
  // 默认近 4 年: 全量 2020 起在容器内加载峰值过高(4.4GB 库 → 8G 限制仍紧), 近 4 年约 2/3 内存更稳
  const [gbmStartYear, setGbmStartYear] = useState(2022)
  const [gbmEndYear, setGbmEndYear] = useState(2027)
  const [gbmTask, setGbmTask] = useState<MLGBMTrainTask | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 挂载时: 检查 ML 依赖 + 读最近 gbm 报告 (若存在)
  useEffect(() => {
    api.getMLStatus().then(setStatus).catch(() => setStatus(null))
    api.getMLGBM().then((d) => setGbm(d.success ? d : null)).catch(() => setGbm(null))
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const runAnomaly = async () => {
    setLoading('anomaly')
    setError('')
    try {
      const d = await api.getMLAnomaly(false)
      if (!d.success) { setError(d.error || '异常检测失败'); setAnomaly(null); return }
      setAnomaly(d)
    } catch (e) { setError((e as Error).message) } finally { setLoading('') }
  }

  const runCluster = async () => {
    setLoading('cluster')
    setError('')
    try {
      const d = await api.getMLCluster(k, false)
      if (!d.success) { setError(d.error || '聚类失败'); setCluster(null); return }
      setCluster(d)
    } catch (e) { setError((e as Error).message) } finally { setLoading('') }
  }

  const runGarch = async () => {
    const c = code.trim()
    if (!c) return
    setLoading('garch')
    setError('')
    try {
      const d = await api.getMLGarch(c)
      if (!d.success) { setError(d.error || 'GARCH 失败'); setGarch(null); return }
      setGarch(d)
    } catch (e) { setError((e as Error).message) } finally { setLoading('') }
  }

  const runGbmTrain = async () => {
    if (gbmTask?.status === 'running') return
    setError('')
    try {
      const d = await api.trainMLGBM(gbmStartYear, gbmEndYear)
      if (!d.success || !d.task_id) { setError(d.error || '训练提交失败'); return }
      setGbmTask(d)
      // 轮询任务状态直到完成/失败
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const s = await api.getMLGBMTrainStatus(d.task_id!)
          setGbmTask(s)
          if (s.status === 'done') {
            if (pollRef.current) clearInterval(pollRef.current)
            const report = await api.getMLGBM()
            setGbm(report.success ? report : null)
          } else if (s.status === 'error') {
            if (pollRef.current) clearInterval(pollRef.current)
            setError(s.error || '训练失败')
          }
        } catch (e) {
          if (pollRef.current) clearInterval(pollRef.current)
          setError((e as Error).message)
        }
      }, 3000)
    } catch (e) { setError((e as Error).message) }
  }

  const hasML = (name: keyof MLStatus['available']) => status?.available?.[name]

  const clusterChart = () => {
    if (!cluster?.clusters?.length) return {}
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: cluster.clusters.map((c) => `簇${c.cluster}`) },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
      series: [{
        type: 'bar',
        data: cluster.clusters.map((c) => ({ value: c.share_pct, itemStyle: { color: '#7c3aed' } })),
      }],
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
    }
  }

  const garchChart = () => {
    if (!garch?.series) return {}
    const s = garch.series
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['条件波动率', '日对数收益'] },
      xAxis: { type: 'category', data: s.dates, axisLabel: { show: false } },
      yAxis: [
        { type: 'value', name: '波动率%', axisLabel: { formatter: '{value}%' } },
        { type: 'value', name: '收益', scale: true },
      ],
      series: [
        { name: '条件波动率', type: 'line', data: s.conditional_vol_pct, yAxisIndex: 0, showSymbol: false, lineStyle: { color: '#dc2626', width: 1.2 } },
        { name: '日对数收益', type: 'line', data: s.log_return, yAxisIndex: 1, showSymbol: false, lineStyle: { color: '#3b82f6', width: 0.6 } },
      ],
      grid: { left: 55, right: 55, top: 30, bottom: 30 },
      dataZoom: [{ type: 'inside' }],
    }
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">🧠 ML 模型</h2>
      <p className="text-gray-500 text-sm mb-4">
        LightGBM 排名 · Isolation Forest 异常检测 · K-Means 聚类 · GARCH 波动率
        {status && !status.available.sklearn && (
          <span className="ml-2 text-amber-600">（ML 依赖未安装，请运行 <code className="bg-gray-100 px-1 rounded">uv sync --extra ml</code>）</span>
        )}
      </p>

      <IndicatorGuide
        items={[
          { term: '异常检测', desc: '用 Isolation Forest 找指标画像脱离全市场群体的个股（如放量异动、极端波动）' },
          { term: '聚类', desc: 'K-Means 按指标画像把全市场分成若干同质簇，识别当前风格聚集' },
          { term: 'GARCH', desc: 'GARCH(1,1) 条件波动率估计与预测，可辅助波动率仓位管理' },
          { term: 'LightGBM 排名', desc: '横截面排名模型预测未来收益排名，RankIC 衡量选股能力（训练耗时较长，走命令行）' },
        ]}
      />

      {error && <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>}

      {/* ---- GBM 训练 + 报告 ---- */}
      <section className="mt-6">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">📊 LightGBM 排名</h3>
          <input
            type="number" min={2018} max={2027} value={gbmStartYear}
            onChange={(e) => setGbmStartYear(Number(e.target.value) || 2020)}
            className="w-20 px-2 py-1 border rounded text-sm"
            title="训练起始年份"
          />
          <span className="text-gray-400 text-sm">~</span>
          <input
            type="number" min={2019} max={2027} value={gbmEndYear}
            onChange={(e) => setGbmEndYear(Number(e.target.value) || 2027)}
            className="w-20 px-2 py-1 border rounded text-sm"
            title="训练结束年份(不含上界)"
          />
          <button
            onClick={runGbmTrain}
            disabled={gbmTask?.status === 'running' || !hasML('lightgbm')}
            className="px-4 py-1.5 bg-violet-600 text-white rounded-md text-sm hover:bg-violet-700 disabled:opacity-50"
          >
            {gbmTask?.status === 'running' ? '训练中...' : '开始训练'}
          </button>
          {!hasML('lightgbm') && (
            <span className="text-xs text-amber-600">（lightgbm 未安装，请 uv sync --extra ml）</span>
          )}
        </div>

        {gbmTask?.status === 'running' && (
          <div className="mb-3 p-3 bg-violet-50 rounded-md text-sm text-violet-700">
            <p>⏳ {gbmTask.stage || '训练中'}… <span className="text-violet-500">（全量约 1-3 分钟，请保持页面）</span></p>
            <div className="mt-2 h-2 bg-violet-100 rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full transition-all" style={{ width: `${(gbmTask.total ? gbmTask.progress / gbmTask.total : 0) * 100}%` }} />
            </div>
          </div>
        )}
        {gbmTask?.status === 'error' && (
          <div className="mb-3 p-3 bg-red-50 rounded-md text-sm text-red-700">
            训练失败: {gbmTask.error || '未知错误'}
          </div>
        )}

        {gbm?.report ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium mb-2">RankIC 表现</p>
              {gbm.report.rankic ? (
                <div className="space-y-1 text-sm">
                  <p>RankIC 均值: <b>{fmt(gbm.report.rankic.mean_ic, 4)}</b></p>
                  <p>ICIR: <b>{fmt(gbm.report.rankic.icir, 3)}</b> · t 值: <b>{fmt(gbm.report.rankic.t_stat, 1)}</b></p>
                  <p>正率: {fmt(gbm.report.rankic.positive_rate * 100, 1)}%（{gbm.report.rankic.n_days} 日）</p>
                </div>
              ) : <p className="text-sm text-gray-500">无 RankIC 数据</p>}
              <div className="mt-3 text-sm">
                {gbm.report.backtest?.ml_topn && (
                  <p>Top-N 含费回测: <b className="text-red-600">{fmt(gbm.report.backtest.ml_topn.total_return_pct, 1)}%</b>
                    <span className="text-gray-500">（随机 {fmt(gbm.report.backtest.random_n?.total_return_pct, 1)}% · 等权 {fmt(gbm.report.backtest.equal_weight?.total_return_pct, 1)}%）</span>
                  </p>
                )}
              </div>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium mb-2">Top 特征（gain）</p>
              {(gbm.report.feature_importance_top15 ?? []).slice(0, 8).map(([f, g]) => (
                <p key={f} className="text-xs text-gray-600 flex justify-between">
                  <span>{f}</span><span>{fmt(g, 0)}</span>
                </p>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">暂无训练报告。点「开始训练」在线跑（约 1-3 分钟），或命令行 <code className="bg-gray-100 px-1 rounded">make ml-gbm</code>。</p>
        )}
      </section>

      {/* ---- 异常检测 ---- */}
      <section className="mt-8">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">🔍 异常检测（Isolation Forest）</h3>
          <button
            onClick={runAnomaly}
            disabled={loading === 'anomaly' || !hasML('sklearn')}
            className="px-4 py-1.5 bg-violet-600 text-white rounded-md text-sm hover:bg-violet-700 disabled:opacity-50"
          >
            {loading === 'anomaly' ? '检测中...' : '运行检测'}
          </button>
        </div>
        {anomaly?.success && (
          <>
            <p className="text-sm text-gray-500 mb-3">
              {anomaly.date} · 全市场 {anomaly.total_stocks} 只，异常 <b className="text-red-600">{anomaly.n_anomalies}</b> 只（{fmt(anomaly.n_anomalies / anomaly.total_stocks * 100, 2)}%）
            </p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead><tr className="bg-gray-50">
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">名称</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">代码</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">异常度</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">涨跌%</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">振幅%</th>
                </tr></thead>
                <tbody>
                  {anomaly.top_anomalies.map((a, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="p-2 text-sm">{a.name}</td>
                      <td className="p-2 text-sm text-gray-500">{a.code}</td>
                      <td className="p-2 text-sm">{fmt(a.severity, 1)}</td>
                      <td className={`p-2 text-sm ${a.change_percent >= 0 ? 'text-red-600' : 'text-green-600'}`}>{fmt(a.change_percent)}</td>
                      <td className="p-2 text-sm">{fmt(a.amplitude)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* ---- 聚类 ---- */}
      <section className="mt-8">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">🗂️ 聚类（K-Means）</h3>
          <input
            type="number" min={2} max={15} value={k}
            onChange={(e) => setK(Math.max(2, Math.min(15, Number(e.target.value) || 6)))}
            className="w-16 px-2 py-1 border rounded text-sm"
          />
          <button
            onClick={runCluster}
            disabled={loading === 'cluster' || !hasML('sklearn')}
            className="px-4 py-1.5 bg-violet-600 text-white rounded-md text-sm hover:bg-violet-700 disabled:opacity-50"
          >
            {loading === 'cluster' ? '聚类中...' : '运行聚类'}
          </button>
        </div>
        {cluster?.success && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="h-64">
              <ReactECharts option={clusterChart()} style={{ height: '100%' }} />
            </div>
            <div>
              <table className="w-full border-collapse">
                <thead><tr className="bg-gray-50">
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">簇</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">只数</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">占比%</th>
                  <th className="p-2 text-left text-xs font-semibold text-gray-500">均涨%</th>
                </tr></thead>
                <tbody>
                  {cluster.clusters.map((c) => (
                    <tr key={c.cluster} className="border-b border-gray-100">
                      <td className="p-2 text-sm">簇{c.cluster}</td>
                      <td className="p-2 text-sm">{c.size}</td>
                      <td className="p-2 text-sm">{fmt(c.share_pct)}</td>
                      <td className={`p-2 text-sm ${c.avg_change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>{fmt(c.avg_change_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* ---- GARCH ---- */}
      <section className="mt-8">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">📉 GARCH 波动率</h3>
          <input
            value={code} onChange={(e) => setCode(e.target.value)}
            placeholder="股票代码 600000" className="w-36 px-2 py-1 border rounded text-sm"
          />
          <button
            onClick={runGarch}
            disabled={loading === 'garch' || !hasML('arch')}
            className="px-4 py-1.5 bg-violet-600 text-white rounded-md text-sm hover:bg-violet-700 disabled:opacity-50"
          >
            {loading === 'garch' ? '计算中...' : '计算'}
          </button>
        </div>
        {garch?.success && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">当前条件波动率</p><p className="text-lg font-semibold">{fmt(garch.summary.current_conditional_vol_pct, 3)}%</p></div>
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">未来{garch.summary.horizon_days}日预测</p><p className="text-lg font-semibold">{fmt(garch.summary.forecast_vol_pct, 3)}%</p></div>
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">年化波动率</p><p className="text-lg font-semibold">{fmt(garch.summary.annualized_vol_pct)}%</p></div>
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">已实现 30 日年化</p><p className="text-lg font-semibold">{fmt(garch.summary.realized_vol_30d_pct)}%</p></div>
            </div>
            <div className="text-xs text-gray-500 mb-2">
              α={fmt(garch.summary.params.alpha, 3)} · β={fmt(garch.summary.params.beta, 3)} · 持续性={fmt(garch.summary.params.persistence, 3)} · AIC={fmt(garch.summary.aic, 1)}
            </div>
            {garch.series && (
              <div className="h-72">
                <ReactECharts option={garchChart()} style={{ height: '100%' }} />
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
