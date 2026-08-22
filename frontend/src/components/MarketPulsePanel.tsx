import { FC, useState, useEffect, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { MarketHistory } from '@/types'
import { api } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'

const RANGES = [
  { days: 30, label: '近30天' },
  { days: 90, label: '近90天' },
  { days: 180, label: '近180天' },
]

// 通用折线/柱状 axis 样式
const baseAxis = (data: (string | number)[]) => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 20, top: 30, bottom: 34 },
  xAxis: { type: 'category', data, boundaryGap: false, axisLabel: { fontSize: 11, color: '#888' } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 11, color: '#888' } },
})

export const MarketPulsePanel: FC = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [days, setDays] = useState(90)
  const [result, setResult] = useState<MarketHistory | null>(null)
  const [rangeLabel, setRangeLabel] = useState('近90天')

  const load = async (d = days, label = rangeLabel) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getMarketHistory(d)
      if (!data.success) { setError(data.error || '加载失败'); return }
      setResult(data)
      setRangeLabel(label)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(90, '近90天')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const pickRange = (d: number, label: string) => {
    setDays(d)
    load(d, label)
  }

  const charts = useMemo(() => {
    if (!result) return []
    const dates = result.dates

    return [
      {
        title: '全市场平均收盘',
        sub: '全部个股收盘价的日均值，叠加快/慢均线看趋势',
        option: {
          ...baseAxis(dates),
          color: ['#e8563f', '#4B3FE3', '#f5a623'],
          series: [
            {
              name: '均价', type: 'line', data: result.avg_close, smooth: true, symbol: 'none',
              lineStyle: { width: 2, color: '#e8563f' },
            },
            {
              name: 'MA5', type: 'line', data: result.avg_ma5, smooth: true, symbol: 'none',
              lineStyle: { width: 1.5, color: '#4B3FE3' },
            },
            {
              name: 'MA20', type: 'line', data: result.avg_ma20, smooth: true, symbol: 'none',
              lineStyle: { width: 1.5, color: '#f5a623' },
            },
          ],
        },
      },
      {
        title: '日度涨跌 + 市场广度',
        sub: '柱=全市场平均涨跌幅(红涨绿跌)，线=上涨家数占比%',
        option: {
          ...baseAxis(dates),
          xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11, color: '#888' } },
          yAxis: [
            { type: 'value', name: '涨跌幅%', axisLabel: { fontSize: 11, color: '#888' }, splitLine: { show: true } },
            { type: 'value', name: '广度%', min: 0, max: 100, axisLabel: { fontSize: 11, color: '#888' } },
          ],
          series: [
            {
              name: '涨跌幅', type: 'bar', data: result.avg_change.map((v) => (v ?? 0)),
              itemStyle: { color: (p: { value: number }) => (p.value >= 0 ? '#e8563f' : '#19be6b') },
            },
            {
              name: '市场广度', type: 'line', yAxisIndex: 1, data: result.breadth, smooth: true, symbol: 'none',
              lineStyle: { width: 2, color: '#4B3FE3' },
            },
          ],
        },
      },
      {
        title: '全市场平均 RSI',
        sub: '0-100 动能强弱，虚线为 30/70 超卖超买分界',
        option: {
          ...baseAxis(dates),
          color: ['#4B3FE3'],
          series: [
            {
              name: 'RSI', type: 'line', data: result.avg_rsi, smooth: true, symbol: 'none',
              lineStyle: { width: 2, color: '#4B3FE3' },
              markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: { type: 'dashed', width: 1 },
                data: [
                  { yAxis: 30, label: { formatter: '超卖', fontSize: 10, color: '#888' } },
                  { yAxis: 70, label: { formatter: '超买', fontSize: 10, color: '#888' } },
                  { yAxis: 50, label: { formatter: '中性', fontSize: 10, color: '#888' } },
                ],
              },
            },
          ],
        },
      },
      {
        title: '市场波动率',
        sub: '近20日平均涨跌幅的标准差，越大代表盘面越剧烈',
        option: {
          ...baseAxis(dates),
          color: ['#f5a623'],
          series: [
            {
              name: '波动率', type: 'line', data: result.volatility, smooth: true, symbol: 'none',
              lineStyle: { width: 2, color: '#f5a623' },
              areaStyle: { opacity: 0.12, color: '#f5a623' },
            },
          ],
        },
      },
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result])

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h2 className="text-xl font-semibold">📈 市场脉搏</h2>
        <div className="flex items-center gap-2">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => pickRange(r.days, r.label)}
              className={`px-3 py-1 rounded-full text-xs ${
                days === r.days ? 'bg-violet-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-gray-500 text-sm mb-4">用图表直观呈现全市场近期的整体温度与节奏</p>

      <IndicatorGuide
        items={[
          { term: '全市场平均收盘', desc: '把当天所有股票收盘价取平均，代表大盘的整体点位水平' },
          { term: 'MA5 / MA20', desc: '5日、20日的均价线，价在线上为多头（偏强）、线下为空头（偏弱），短期线在长期线上方是健康的多头排列' },
          { term: '日度涨跌幅', desc: '全市场当天涨跌幅的平均值，柱子在零轴上为红色（涨）、下方为绿色（跌）' },
          { term: '市场广度', desc: '当天上涨股票占全市场的比例(%)，60%以上一般是普涨行情，<50%说明赚钱效应偏弱' },
          { term: 'RSI 强弱', desc: '0-100 的涨跌力量比值，>70 超买（过热小心回调），<30 超卖（超跌可能反弹），50 附近中性' },
          { term: '波动率', desc: '近20日涨跌幅度的标准差，衡量盘面晃得有多厉害；越高风险越大、越难拿住' },
        ]}
      />

      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}
      {loading && <div className="py-10 text-gray-400 text-sm text-center">加载中...</div>}

      {!loading && result && result.success && (
        <>
          <div className="mb-4 text-xs text-gray-500">
            {rangeLabel} · {result.start_date} ~ {result.end_date}（{result.days} 个交易日）
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {charts.map((c, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-3">
                <h3 className="font-semibold text-sm mb-0.5">{c.title}</h3>
                <p className="text-xs text-gray-400 mb-3">{c.sub}</p>
                <div className="h-60">
                  <ReactECharts option={c.option} style={{ height: '100%' }} notMerge />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}