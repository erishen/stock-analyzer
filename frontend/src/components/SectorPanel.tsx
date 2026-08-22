import { FC, useState, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { SectorResult } from '@/types'
import { api } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'

export const SectorPanel: FC = () => {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SectorResult | null>(null)
  const [error, setError] = useState('')

  const handleAnalyze = async (refresh = false) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getSector(refresh)
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  // 挂载时自动加载 (面板常驻, 走后端缓存瞬显, 不重复计算)
  useEffect(() => {
    handleAnalyze(false)
  }, [])

  const getStrengthColor = (strength: string): string => {
    switch (strength) {
      case 'strong': return 'bg-green-100 text-green-800'
      case 'weak': return 'bg-red-100 text-red-800'
      default: return 'bg-yellow-100 text-yellow-800'
    }
  }

  const getBarChartOption = () => {
    if (!result?.sectors?.length) return {}
    const top10 = result.sectors.slice(0, 10)
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        data: top10.map(s => s.name.substring(0, 4)),
        axisLabel: { rotate: 45 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: '{value}%' },
      },
      series: [{
        type: 'bar',
        data: top10.map(s => ({
          value: s.momentum,
          itemStyle: { color: s.momentum >= 0 ? '#ef4444' : '#10b981' },
        })),
      }],
      grid: { left: 50, right: 20, top: 20, bottom: 50 },
    }
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">行业轮动</h2>
      <p className="text-gray-500 text-sm mb-4">分析行业强弱，发现轮动机会</p>

      <IndicatorGuide
        items={[
          { term: '动量', desc: '行业近期的整体涨幅(%)，正数表示近期在走强(红)，负数表示在走弱(绿)，越高轮动热度越强' },
          { term: '强度(强/中/弱)', desc: '行业上涨的力度等级，强=上涨动能明显，弱=持续下跌' },
          { term: '股票数', desc: '该行业包含的股票数量，用于判断板块容量与代表性' },
          { term: '建仓/持有/减仓/清仓', desc: '针对该行业的轮动操作建议：建仓=开始进入，持有=继续拿，减仓=减少投入，清仓=全部退出' },
        ]}
      />

      <div className="flex items-center gap-3">
        <button
          onClick={() => handleAnalyze(false)}
          disabled={loading}
          className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? '分析中...' : '分析行业'}
        </button>
        {result && result.success && (
          <button
            onClick={() => handleAnalyze(true)}
            disabled={loading}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
          >
            重新计算
          </button>
        )}
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <p className="text-sm text-gray-500 mb-4">分析日期: {result.analysis_date}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
            <div>
              <h3 className="font-semibold mb-3">行业动量排名</h3>
              <div className="h-80">
                <ReactECharts option={getBarChartOption()} style={{ height: '100%' }} />
              </div>
            </div>

            <div>
              <h3 className="font-semibold mb-3">行业详情</h3>
              <div>
                <table className="w-full border-collapse">
                  <thead className="sticky top-0 bg-white">
                    <tr className="bg-gray-50">
                      <th className="p-2 text-left text-xs font-semibold text-gray-500">行业</th>
                      <th className="p-2 text-left text-xs font-semibold text-gray-500">动量</th>
                      <th className="p-2 text-left text-xs font-semibold text-gray-500">强度</th>
                      <th className="p-2 text-left text-xs font-semibold text-gray-500">股票数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.sectors.map((s, i) => (
                      <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="p-2 text-sm">{s.name}</td>
                        <td className={`p-2 text-sm ${s.momentum >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {s.momentum >= 0 ? '+' : ''}{s.momentum.toFixed(2)}%
                        </td>
                        <td className="p-2">
                          <span className={`px-2 py-1 text-xs rounded ${getStrengthColor(s.strength)}`}>
                            {s.strength === 'strong' ? '强' : s.strength === 'weak' ? '弱' : '中'}
                          </span>
                        </td>
                        <td className="p-2 text-sm">{s.stock_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {result.rotation_signals?.length > 0 && (
            <div>
              <h3 className="font-semibold mb-3">轮动信号</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {result.rotation_signals.map((s, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-sm font-medium">
                      {s.sector}
                      <span
                        className={`ml-2 px-2 py-0.5 text-xs rounded ${
                          s.signal === 'enter'
                            ? 'bg-green-100 text-green-800'
                            : s.signal === 'exit'
                              ? 'bg-red-100 text-red-800'
                              : s.signal === 'hold'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {{ enter: '建仓', hold: '持有', reduce: '减仓', exit: '清仓' }[s.signal] ?? s.signal}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      评分: {s.score} | {s.reason}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
