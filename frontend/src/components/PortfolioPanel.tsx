import { FC, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { PortfolioResult } from '@/types'
import { api } from '@/services/api'

const weightMethods = [
  { value: 'equal', label: '等权分配' },
  { value: 'risk_parity', label: '风险平价' },
  { value: 'sharpe', label: '夏普加权' },
]

export const PortfolioPanel: FC = () => {
  const [weightMethod, setWeightMethod] = useState('equal')
  const [holdingDays, setHoldingDays] = useState(5)
  const [capital, setCapital] = useState(100000)
  const [strategies, setStrategies] = useState({
    momentum: true,
    mean_reversion: true,
    trend_following: true,
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PortfolioResult | null>(null)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    const selectedStrategies = Object.entries(strategies)
      .filter(([, v]) => v)
      .map(([k]) => k)

    if (selectedStrategies.length === 0) {
      setError('请至少选择一个策略')
      return
    }

    setLoading(true)
    setError('')
    try {
      const data = await api.runPortfolio({
        strategies: selectedStrategies,
        weight_method: weightMethod,
        holding_days: holdingDays,
        initial_capital: capital,
      })
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const getWeightChartOption = () => {
    if (!result?.strategy_weights) return {}
    const data = Object.entries(result.strategy_weights).map(([name, value]) => ({
      name,
      value: (value * 100).toFixed(1),
    }))
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: data.map(d => ({ name: d.name, value: parseFloat(d.value) })),
        label: { formatter: '{b}\n{c}%' },
      }],
      color: ['#7c3aed', '#10b981', '#f59e0b', '#ef4444'],
    }
  }

  const getCorrelationColor = (v: number): string => {
    if (v === 1) return 'bg-violet-500 text-white'
    if (v > 0.5) return 'bg-green-100 text-green-800'
    if (v > 0) return 'bg-yellow-100 text-yellow-800'
    return 'bg-red-100 text-red-800'
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">组合分析</h2>
      <p className="text-gray-500 text-sm mb-4">多策略组合回测，优化资产配置</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">权重方法</label>
          <select
            value={weightMethod}
            onChange={(e) => setWeightMethod(e.target.value)}
            className="p-2 border border-gray-200 rounded-md"
          >
            {weightMethods.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">持有天数</label>
          <input
            type="number"
            value={holdingDays}
            onChange={(e) => setHoldingDays(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">初始资金</label>
          <input
            type="number"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="text-xs text-gray-500 mb-2 block">策略组合</label>
        <div className="flex gap-4">
          {[
            { key: 'momentum', label: '动量策略' },
            { key: 'mean_reversion', label: '均值回归' },
            { key: 'trend_following', label: '趋势跟踪' },
          ].map((s) => (
            <label key={s.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={strategies[s.key as keyof typeof strategies]}
                onChange={(e) => setStrategies({ ...strategies, [s.key]: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">{s.label}</span>
            </label>
          ))}
        </div>
      </div>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
      >
        {loading ? '分析中...' : '开始分析'}
      </button>

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            {[
              { label: '总收益率', value: `${result.total_return >= 0 ? '+' : ''}${result.total_return.toFixed(2)}%`, color: result.total_return >= 0 ? 'text-green-600' : 'text-red-600' },
              { label: '夏普比率', value: result.sharpe_ratio.toFixed(2), color: '' },
              { label: '最大回撤', value: `-${result.max_drawdown.toFixed(2)}%`, color: 'text-red-600' },
              { label: '分散度', value: result.diversification_ratio.toFixed(2), color: '' },
            ].map((item, i) => (
              <div key={i} className="text-center p-4 bg-gray-50 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">{item.label}</div>
                <div className={`text-lg font-semibold ${item.color}`}>{item.value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <h3 className="font-semibold mb-3">策略权重分布</h3>
              <div className="h-64">
                <ReactECharts option={getWeightChartOption()} style={{ height: '100%' }} />
              </div>
            </div>

            <div>
              <h3 className="font-semibold mb-3">策略表现对比</h3>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="p-2 text-left text-xs font-semibold text-gray-500">策略</th>
                    <th className="p-2 text-left text-xs font-semibold text-gray-500">权重</th>
                    <th className="p-2 text-left text-xs font-semibold text-gray-500">收益率</th>
                    <th className="p-2 text-left text-xs font-semibold text-gray-500">夏普</th>
                  </tr>
                </thead>
                <tbody>
                  {result.strategy_results.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="p-2 text-sm">{r.name}</td>
                      <td className="p-2 text-sm">
                        {((result.strategy_weights[r.name.replace('Strategy', '').toLowerCase()] || 0) * 100).toFixed(1)}%
                      </td>
                      <td className={`p-2 text-sm ${r.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {r.total_return >= 0 ? '+' : ''}{r.total_return.toFixed(2)}%
                      </td>
                      <td className="p-2 text-sm">{r.sharpe_ratio.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {result.correlation_matrix && (
            <div className="mt-5">
              <h3 className="font-semibold mb-3">策略相关性矩阵</h3>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="p-2"></th>
                      {Object.keys(result.correlation_matrix).map((k) => (
                        <th key={k} className="p-2 text-center">{k.substring(0, 8)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.correlation_matrix).map(([k1, row]) => (
                      <tr key={k1}>
                        <td className="p-2 font-medium">{k1.substring(0, 8)}</td>
                        {Object.entries(row).map(([k2, v]) => (
                          <td key={k2} className={`p-2 text-center rounded ${getCorrelationColor(v)}`}>
                            {v.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
