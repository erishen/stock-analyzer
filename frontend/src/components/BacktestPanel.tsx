import { FC, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { BacktestResult, Trade } from '@/types'
import { api } from '@/services/api'

const strategies = [
  { value: 'momentum', label: '动量策略' },
  { value: 'mean_reversion', label: '均值回归策略' },
  { value: 'trend_following', label: '趋势跟踪策略' },
  { value: 'multi_factor', label: '多因子策略' },
]

export const BacktestPanel: FC = () => {
  const [strategy, setStrategy] = useState('momentum')
  const [holdingDays, setHoldingDays] = useState(5)
  const [capital, setCapital] = useState(100000)
  const [minPrice, setMinPrice] = useState(2)
  const [stopLoss, setStopLoss] = useState(0)
  const [takeProfit, setTakeProfit] = useState(0)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')

  const handleBacktest = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.runBacktest({
        strategy,
        holding_days: holdingDays,
        initial_capital: capital,
        min_price: minPrice,
        stop_loss: stopLoss / 100,
        take_profit: takeProfit / 100,
      })
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">策略类型</label>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
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
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">最低价格</label>
          <input
            type="number"
            value={minPrice}
            onChange={(e) => setMinPrice(Number(e.target.value))}
            step="0.5"
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
            onChange={(e) => setStopLoss(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">止盈比例 (%)</label>
          <input
            type="number"
            value={takeProfit}
            onChange={(e) => setTakeProfit(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
      </div>

      <button
        onClick={handleBacktest}
        disabled={loading}
        className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
      >
        {loading ? '回测中...' : '开始回测'}
      </button>

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mb-5">
            {[
              { label: '总收益率', value: `${result.total_return >= 0 ? '+' : ''}${result.total_return.toFixed(2)}%`, color: result.total_return >= 0 ? 'text-green-600' : 'text-red-600' },
              { label: '年化收益', value: `${result.annualized_return >= 0 ? '+' : ''}${result.annualized_return.toFixed(2)}%`, color: result.annualized_return >= 0 ? 'text-green-600' : 'text-red-600' },
              { label: '最大回撤', value: `-${result.max_drawdown.toFixed(2)}%`, color: 'text-red-600' },
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
                    <td className="p-3 text-sm">{t.code}</td>
                    <td className="p-3 text-sm">{t.name}</td>
                    <td className="p-3 text-sm">{t.entry_date}</td>
                    <td className="p-3 text-sm">{t.entry_price.toFixed(2)}</td>
                    <td className="p-3 text-sm">{t.exit_price.toFixed(2)}</td>
                    <td className={`p-3 text-sm ${t.profit_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {t.profit_percent >= 0 ? '+' : ''}{t.profit_percent.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
