import { FC, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { MarketTimingResult } from '@/types'
import { api } from '@/services/api'

export const MarketTimingPanel: FC = () => {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<MarketTimingResult | null>(null)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getMarketTiming()
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const getStateInfo = (state: string) => {
    switch (state) {
      case 'bull': return { label: '牛市', color: 'text-green-600', bgColor: 'bg-green-100' }
      case 'bear': return { label: '熊市', color: 'text-red-600', bgColor: 'bg-red-100' }
      default: return { label: '震荡', color: 'text-yellow-600', bgColor: 'bg-yellow-100' }
    }
  }

  const getGaugeOption = () => {
    if (!result) return {}
    return {
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 4,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.25, '#ef4444'],
              [0.5, '#f59e0b'],
              [0.75, '#10b981'],
              [1, '#22c55e'],
            ],
          },
        },
        pointer: { width: 5 },
        axisTick: { show: false },
        splitLine: { length: 15, lineStyle: { width: 2, color: '#999' } },
        axisLabel: { distance: 25, fontSize: 10 },
        detail: { valueAnimation: true, formatter: '{value}', fontSize: 24, offsetCenter: [0, '70%'] },
        data: [{ value: result.score, name: '综合评分' }],
      }],
    }
  }

  const getSignalColor = (signal: string): string => {
    switch (signal) {
      case 'bullish': return 'bg-green-100 text-green-800'
      case 'bearish': return 'bg-red-100 text-red-800'
      default: return 'bg-yellow-100 text-yellow-800'
    }
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">大盘择时</h2>
      <p className="text-gray-500 text-sm mb-4">判断市场状态，指导仓位配置</p>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
      >
        {loading ? '分析中...' : '分析大盘'}
      </button>

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="text-center">
              <div className="h-64">
                <ReactECharts option={getGaugeOption()} style={{ height: '100%' }} />
              </div>
              <div className="mt-4">
                <span className={`inline-block px-4 py-2 rounded-lg text-lg font-semibold ${getStateInfo(result.state).bgColor} ${getStateInfo(result.state).color}`}>
                  {getStateInfo(result.state).label}
                </span>
              </div>
            </div>

            <div>
              <h3 className="font-semibold mb-3">仓位建议</h3>
              <div className="p-4 bg-gray-50 rounded-lg mb-4">
                <p className="text-gray-700">{result.position_advice}</p>
              </div>

              <h3 className="font-semibold mb-3">指标详情</h3>
              <div className="space-y-2">
                {Object.entries(result.indicators).map(([name, ind]) => (
                  <div key={name} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="text-sm">{name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{ind.value}</span>
                      <span className={`px-2 py-1 text-xs rounded ${getSignalColor(ind.signal)}`}>
                        {ind.signal === 'bullish' ? '看涨' : ind.signal === 'bearish' ? '看跌' : '中性'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
