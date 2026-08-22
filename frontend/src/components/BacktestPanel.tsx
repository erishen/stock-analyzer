import { FC, useState, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { BacktestResult, OptimizeResult, OptimizeTask, Trade } from '@/types'
import { api } from '@/services/api'
import { StockDetailModal } from './StockDetailModal'
import { IndicatorGuide } from './IndicatorGuide'

const strategies = [
  { value: 'momentum', label: '动量策略' },
  { value: 'mean_reversion', label: '均值回归策略' },
  { value: 'trend_following', label: '趋势跟踪策略' },
  { value: 'multi_factor', label: '多因子策略' },
]

export const BacktestPanel: FC = () => {
  // 参数持久化: 统一存 localStorage['backtest_params'] (JSON), 刷新/重挂载后恢复上次选择
  const loadParam = () => {
    try {
      return JSON.parse(localStorage.getItem('backtest_params') || '{}')
    } catch {
      return {}
    }
  }
  const [params, setParams] = useState<Record<string, unknown>>(() => loadParam())

  const [strategy, setStrategy] = useState(() => loadParam().strategy ?? localStorage.getItem('backtest_strategy') ?? 'momentum')
  const persistStrategy = (v: string) => {
    setStrategy(v)
    setParams((p) => ({ ...p, strategy: v }))
  }
  const [holdingDays, setHoldingDays] = useState(() => Number(loadParam().holding_days ?? 20))
  const [capital, setCapital] = useState(() => Number(loadParam().capital ?? 100000))
  const [startDate, setStartDate] = useState(() => String(loadParam().start_date ?? ''))
  const [endDate, setEndDate] = useState(() => String(loadParam().end_date ?? ''))
  const [minPrice, setMinPrice] = useState(() => Number(loadParam().min_price ?? 2))
  const [stopLoss, setStopLoss] = useState(() => Number(loadParam().stop_loss_pct ?? 15))
  const [takeProfit, setTakeProfit] = useState(() => Number(loadParam().take_profit_pct ?? 30))
  const [hasSavedDates, setHasSavedDates] = useState(() => Boolean(loadParam().end_date || loadParam().start_date))

  // 任一参数变更时持久化 (params 累积, 每次仅同步最新全部值)
  useEffect(() => {
    localStorage.setItem('backtest_params', JSON.stringify(params))
  }, [params])
  const persist = (patch: Record<string, unknown>) => setParams((p) => ({ ...p, ...patch }))
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [optimizeProgress, setOptimizeProgress] = useState({ done: 0, total: 0, stage: '' })
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)

  const doBacktest = async (refresh: boolean, start: string, end: string, strategyOverride?: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.runBacktest({
        strategy: strategyOverride ?? strategy,
        holding_days: holdingDays,
        initial_capital: capital,
        min_price: minPrice,
        stop_loss: stopLoss / 100,
        take_profit: takeProfit / 100,
        start_date: start || undefined,
        end_date: end || undefined,
        refresh: refresh,
      })
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleBacktest = async (refresh = false) => {
    await doBacktest(refresh, startDate, endDate)
  }

  const handleOptimize = async () => {
    if (!['momentum', 'mean_reversion'].includes(strategy)) {
      setError(`自动寻优暂只支持动量策略、均值回归策略（当前为 ${strategies.find((s) => s.value === strategy)?.label}）`)
      return
    }
    setOptimizing(true)
    setError('')
    setOptimizeResult(null)
    setOptimizeProgress({ done: 0, total: 0, stage: '' })
    try {
      const task = await api.runOptimize({
        strategy,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        initial_capital: capital,
      })
      if (!task.success || !task.task_id) {
        setError(task.error || '寻优提交失败')
        return
      }
      // 轮询任务状态 (最多 5 分钟; 完成/失败即停止)
      const interval = setInterval(async () => {
        let st: OptimizeTask
        try {
          st = await api.optimizeStatus(task.task_id!)
        } catch {
          clearInterval(interval)
          return
        }
        if (st.progress > 0 || st.stage) setOptimizeProgress({ done: st.progress, total: st.total, stage: st.stage })
        if (st.status === 'done') {
          clearInterval(interval)
          setOptimizing(false)
          if (st.result) setOptimizeResult(st.result)
        } else if (st.status === 'error') {
          clearInterval(interval)
          setOptimizing(false)
          setError(st.error || '寻优失败')
        }
      }, 1500)
      setTimeout(() => {
        clearInterval(interval)
        setOptimizing(false)
      }, 5 * 60 * 1000)
    } catch (e) {
      setError((e as Error).message)
      setOptimizing(false)
    }
  }

  // 挂载时: 有已保存日期则直接首算; 否则拉取数据范围填充默认值再回测
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      let start = startDate
      let end = endDate
      if (!hasSavedDates) {
        try {
          const data = await api.getStats()
          if (data?.success) {
            start = data.min_date || ''
            end = data.max_date || ''
            if (!cancelled) {
              setStartDate(start)
              setEndDate(end)
            }
          }
        } catch {
          // 拉取失败时保持空, 回退全历史
        }
      }
      if (!cancelled) await doBacktest(false, start, end)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const getEquityChartOption = () => {
    if (!result?.equity_curve?.length) return {}
    return {
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: result.equity_curve.map(e => e.date),
        show: false,
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (v: number) => (v / 1000).toFixed(0) + 'K' },
      },
      series: [{
        type: 'line',
        data: result.equity_curve.map(e => e.equity),
        smooth: true,
        areaStyle: { opacity: 0.3 },
        lineStyle: { color: '#7c3aed' },
        itemStyle: { color: '#7c3aed' },
      }],
      grid: { left: 50, right: 20, top: 20, bottom: 20 },
    }
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">策略回测</h2>
      <p className="text-gray-500 text-sm mb-4">运行策略回测，评估策略表现</p>

      <IndicatorGuide
        items={[
          { term: '收益曲线', desc: '按该策略规则历史交易后，账户资金从起点到当前的变化走势，越平稳向上越好' },
          { term: '总收益率', desc: '整个回测期间账户的累计涨跌幅(红涨绿跌)' },
          { term: '最大回撤', desc: '历史中从最高点跌下来的最大幅度，越小代表账户波动越稳、抗跌越好' },
          { term: '夏普比率', desc: '每承受一单位风险获得的收益，>1 较好，越高越划算' },
          { term: '胜率', desc: '所有交易中盈利单所占比例，不代表一切，但要结合盈亏比看' },
          { term: '交易记录', desc: '策略实际发出的每一笔买卖明细，点击代码/名称可看个股详情' },
        ]}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">策略类型</label>
          <select
            value={strategy}
            onChange={(e) => {
              const next = e.target.value
              persistStrategy(next)
              if (result) void doBacktest(false, startDate, endDate, next)
            }}
            className="p-2 border border-gray-200 rounded-md"
          >
            {strategies.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">持有天数</label>
          <input
            type="number"
            value={holdingDays}
            onChange={(e) => {
              setHoldingDays(Number(e.target.value))
              persist({ holding_days: Number(e.target.value) })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">初始资金</label>
          <input
            type="number"
            value={capital}
            onChange={(e) => {
              setCapital(Number(e.target.value))
              persist({ capital: Number(e.target.value) })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">最低价格</label>
          <input
            type="number"
            value={minPrice}
            onChange={(e) => {
              setMinPrice(Number(e.target.value))
              persist({ min_price: Number(e.target.value) })
            }}
            step="0.5"
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">开始日期</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value)
              setHasSavedDates(true)
              persist({ start_date: e.target.value })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">结束日期</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value)
              setHasSavedDates(true)
              persist({ end_date: e.target.value })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">止损比例 (%)</label>
          <input
            type="number"
            value={stopLoss}
            onChange={(e) => {
              setStopLoss(Number(e.target.value))
              persist({ stop_loss_pct: Number(e.target.value) })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">止盈比例 (%)</label>
          <input
            type="number"
            value={takeProfit}
            onChange={(e) => {
              setTakeProfit(Number(e.target.value))
              persist({ take_profit_pct: Number(e.target.value) })
            }}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => handleBacktest(false)}
          disabled={loading || optimizing}
          className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? '回测中...' : '开始回测'}
        </button>
        {result && result.success && (
          <button
            onClick={() => handleBacktest(true)}
            disabled={loading || optimizing}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
          >
            重新回测
          </button>
        )}
        <button
          onClick={handleOptimize}
          disabled={loading || optimizing}
          className="px-4 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50"
        >
          {optimizing ? '寻优中...' : '自动寻优'}
        </button>
      </div>

      {optimizing && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>{optimizeProgress.stage || '正在按训练/验证分段扫描参数组合...'}</span>
            {optimizeProgress.total > 0 && (
              <span>{optimizeProgress.done}/{optimizeProgress.total}</span>
            )}
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all duration-300"
              style={{
                width: optimizeProgress.total > 0
                  ? `${Math.round((optimizeProgress.done / optimizeProgress.total) * 100)}%`
                  : '3%',
              }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {optimizeResult && optimizeResult.success && (
        <div className="mt-5 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg">自动寻优结果</h3>
            <span className="text-xs text-gray-500">扫描 {optimizeResult.total_combinations} 组参数</span>
          </div>
          <div className="text-sm mb-3 text-gray-600">
            <span className="mr-4">训练段：{optimizeResult.train_start} ~ {optimizeResult.train_end}</span>
            <span>验证段：{optimizeResult.val_start} ~ {optimizeResult.val_end}</span>
          </div>
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-1">最优参数</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(optimizeResult.best_params).map(([k, v]) => (
                <span key={k} className="px-2 py-1 bg-white border border-emerald-300 rounded-md text-sm">
                  {k}: <b>{v}</b>
                </span>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {[
              { label: '训练收益', v: `${optimizeResult.best_return >= 0 ? '+' : ''}${optimizeResult.best_return.toFixed(2)}%`, c: optimizeResult.best_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '训练夏普', v: optimizeResult.best_sharpe.toFixed(2), c: optimizeResult.best_sharpe > 0 ? 'text-red-600' : 'text-green-600' },
              { label: '训练回撤', v: `-${optimizeResult.best_drawdown.toFixed(2)}%`, c: 'text-green-600' },
              { label: '验证收益', v: `${optimizeResult.val_return >= 0 ? '+' : ''}${optimizeResult.val_return.toFixed(2)}%`, c: optimizeResult.val_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '验证夏普', v: optimizeResult.val_sharpe.toFixed(2), c: optimizeResult.val_sharpe > 0 ? 'text-red-600' : 'text-green-600' },
              { label: '验证回撤', v: `-${optimizeResult.val_drawdown.toFixed(2)}%`, c: 'text-green-600' },
            ].map((it, i) => (
              <div key={i} className="text-center p-3 bg-white rounded-lg">
                <div className="text-xs text-gray-500 mb-1">{it.label}</div>
                <div className={`text-base font-semibold ${it.c}`}>{it.v}</div>
              </div>
            ))}
          </div>
          {optimizeResult.top_results.length > 0 && (
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-gray-600">查看 Top 10 参数组合</summary>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-xs text-gray-700">
                  <thead>
                    <tr className="border-b">
                      {Object.keys(optimizeResult.top_results[0].params).map((k) => <th key={k} className="text-left py-1 px-2">{k}</th>)}
                      <th className="text-left py-1 px-2">收益</th>
                      <th className="text-left py-1 px-2">夏普</th>
                      <th className="text-left py-1 px-2">回撤</th>
                      <th className="text-left py-1 px-2">胜率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optimizeResult.top_results.map((row, i) => (
                      <tr key={i} className="border-b">
                        {Object.values(row.params).map((v, j) => <td key={j} className="py-1 px-2">{v}</td>)}
                        <td className="py-1 px-2">{row.total_return.toFixed(2)}%</td>
                        <td className="py-1 px-2">{row.sharpe_ratio.toFixed(2)}</td>
                        <td className="py-1 px-2">-{row.max_drawdown.toFixed(2)}%</td>
                        <td className="py-1 px-2">{row.win_rate.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <h3 className="font-semibold text-lg mb-4">{strategies.find((s) => s.value === strategy)?.label ?? result.strategy_name}</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mb-5">
            {[
              { label: '总收益率', value: `${result.total_return >= 0 ? '+' : ''}${result.total_return.toFixed(2)}%`, color: result.total_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '年化收益', value: `${result.annualized_return >= 0 ? '+' : ''}${result.annualized_return.toFixed(2)}%`, color: result.annualized_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '最大回撤', value: `-${result.max_drawdown.toFixed(2)}%`, color: 'text-green-600' },
              { label: '夏普比率', value: result.sharpe_ratio.toFixed(2), color: '' },
              { label: '胜率', value: `${result.win_rate.toFixed(1)}%`, color: '' },
              { label: '总交易数', value: result.total_trades.toString(), color: '' },
            ].map((item, i) => (
              <div key={i} className="text-center p-4 bg-gray-50 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">{item.label}</div>
                <div className={`text-lg font-semibold ${item.color}`}>{item.value}</div>
              </div>
            ))}
          </div>

          {result.equity_curve?.length > 0 && (
            <div className="h-64 mb-5">
              <ReactECharts option={getEquityChartOption()} style={{ height: '100%' }} />
            </div>
          )}

          <h3 className="font-semibold mb-3">交易记录</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">代码</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">名称</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">买入日期</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">买入价</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">卖出价</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">收益%</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.slice(0, 20).map((t: Trade, i: number) => (
                  <tr key={i} className="hover:bg-gray-50 border-b border-gray-100">
                    <td className="p-3 text-sm">
                      <button
                        onClick={() => setSelectedCode(t.code)}
                        className="text-violet-600 hover:underline cursor-pointer"
                      >
                        {t.code}
                      </button>
                    </td>
                    <td className="p-3 text-sm">
                      <button
                        onClick={() => setSelectedCode(t.code)}
                        className="hover:text-violet-600 cursor-pointer"
                      >
                        {t.name}
                      </button>
                    </td>
                    <td className="p-3 text-sm">{t.entry_date}</td>
                    <td className="p-3 text-sm">{t.entry_price.toFixed(2)}</td>
                    <td className="p-3 text-sm">{t.exit_price.toFixed(2)}</td>
                    <td className={`p-3 text-sm ${t.profit_percent >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {t.profit_percent >= 0 ? '+' : ''}{t.profit_percent.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedCode && (
        <StockDetailModal code={selectedCode} onClose={() => setSelectedCode(null)} />
      )}
    </div>
  )
}
