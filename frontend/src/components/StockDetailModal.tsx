import { FC, useState, useEffect, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { StockDetail } from '@/types'
import { api } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'

interface Props {
  code: string
  onClose: () => void
}

const fmtVolume = (v: number): string => {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return String(v)
}

// 数值: 空/无效 → '—', 否则保留2位
const fmtNum = (v: number | null | undefined): string =>
  v == null || Number.isNaN(v) ? '—' : `${Number(v).toFixed(2)}`

// 涨跌文案/配色 (A股红涨绿跌)
const retColor = (v: number | null): string =>
  v === null ? 'text-gray-400' : v >= 0 ? 'text-red-600' : 'text-green-600'

const retText = (v: number | null): string =>
  v === null ? '—' : `${v >= 0 ? '+' : ''}${(v as number).toFixed(2)}%`

// K线时间范围 → 需返回的交易日根数
const timeRanges = [
  { key: '3M', label: '近3月', limit: 66 },
  { key: '6M', label: '近6月', limit: 132 },
  { key: '1Y', label: '近1年', limit: 244 },
  { key: '3Y', label: '近3年', limit: 732 },
  { key: '5Y', label: '近5年', limit: 1220 },
  { key: 'ALL', label: '全部', limit: 3000 },
]

export const StockDetailModal: FC<Props> = ({ code, onClose }) => {
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [range, setRange] = useState('6M')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 挂载时锁母页滚动, 卸载时恢复 (避免详情滚动穿透到背景表格)
  useEffect(() => {
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [])

  // days 固定取较大窗口, 保证区间收益能算到 5 年/全部
  const DAYS = 3000
  useEffect(() => {
    if (!code) return
    const target = timeRanges.find((r) => r.key === range) ?? timeRanges[1]
    setLoading(true)
    setError('')
    api.getStockDetail(code, target.limit, DAYS)
      .then((d) => {
        setDetail(d)
        if (!d.success) setError(d.error || '加载失败')
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [code, range])

  const option = useMemo(() => {
    if (!detail?.kline?.length) return {}
    const dates = detail.kline.map((k) => k.date)
    const candles = detail.kline.map((k) => [k.open, k.close, k.low, k.high])
    const volumes = detail.kline.map((k) => k.volume)
    const ma = (field: 'ma5' | 'ma10' | 'ma20' | 'ma60') => detail.kline.map((k) => k[field])

    const maSeries: object[] = [
      { name: 'MA5', data: ma('ma5'), color: '#f59e0b' },
      { name: 'MA10', data: ma('ma10'), color: '#3b82f6' },
      { name: 'MA20', data: ma('ma20'), color: '#8b5cf6' },
      { name: 'MA60', data: ma('ma60'), color: '#64748b' },
    ].map((s) => ({
      type: 'line',
      name: s.name,
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: s.data,
      symbol: 'none',
      lineStyle: { width: 1, color: s.color },
      itemStyle: { color: s.color },
      smooth: true,
    }))

    return {
      animation: false,
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#333' } },
      legend: { data: ['MA5', 'MA10', 'MA20', 'MA60'], top: 0, itemWidth: 14 },
      grid: [
        { left: 60, right: 20, top: 28, height: '58%' },
        { left: 60, right: 20, top: '76%', height: '18%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { color: '#6b7280', fontSize: 10 } },
      ],
      yAxis: [
        { gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#f1f5f9' } } },
        { gridIndex: 1, axisLabel: { color: '#6b7280', fontSize: 10 } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      ],
      series: [
        {
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: candles,
          itemStyle: {
            color: '#ef4444',
            color0: '#10b981',
            borderColor: '#ef4444',
            borderColor0: '#10b981',
          },
        },
        ...maSeries,
        {
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: { color: '#94a3b8' },
        },
      ],
    }
  }, [detail])

  const indicators: Array<{ label: string; value: string }> = detail
    ? [
        { label: 'MA5', value: detail.indicators.ma5.toFixed(2) },
        { label: 'MA10', value: detail.indicators.ma10.toFixed(2) },
        { label: 'MA20', value: detail.indicators.ma20.toFixed(2) },
        { label: 'MA60', value: detail.indicators.ma60.toFixed(2) },
        { label: 'MACD', value: detail.indicators.macd.toFixed(3) },
        { label: 'MACD柱', value: detail.indicators.macd_hist.toFixed(3) },
        { label: 'RSI', value: detail.indicators.rsi.toFixed(2) },
        { label: 'KDJ(K/D/J)', value: `${detail.indicators.kdj_k.toFixed(1)}/${detail.indicators.kdj_d.toFixed(1)}/${detail.indicators.kdj_j.toFixed(1)}` },
        { label: '布林上轨', value: detail.indicators.boll_upper.toFixed(2) },
        { label: '布林中轨', value: detail.indicators.boll_mid.toFixed(2) },
        { label: '布林下轨', value: detail.indicators.boll_lower.toFixed(2) },
        { label: 'ATR', value: detail.indicators.atr.toFixed(2) },
      ]
    : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-[880px] max-w-[95vw] max-h-[90vh] overflow-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部: 滚动时吸顶不动 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-100 sticky top-0 bg-white z-10">
          <div>
            <div className="text-xl font-semibold flex items-center gap-3">
              <span>{detail?.name || code}</span>
              <span className="text-sm text-gray-500">{code}</span>
              {detail?.market && (
                <span className="px-2 py-0.5 text-xs rounded bg-violet-100 text-violet-700">{detail.market}</span>
              )}
            </div>
            {detail?.latest && detail.latest.date && (
              <div className="text-sm text-gray-500 mt-1">交易日 {detail.latest.date}</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-md text-gray-500 hover:bg-gray-100"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {loading && (
          <div className="p-16 text-center text-gray-400">加载中...</div>
        )}

        {error && !loading && (
          <div className="p-16 text-center text-red-600">{error}</div>
        )}

        {detail?.success && !loading && (
          <div className="p-4">
            {/* 最新行情 + 区间收益 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div className="border border-gray-100 rounded-xl p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <span className="w-1 h-3.5 rounded bg-violet-500" />
                  <span className="text-xs text-gray-500 font-medium">最新行情</span>
                </div>
                <div className="flex items-end justify-between flex-wrap gap-2">
                  <div>
                    <div className="text-3xl font-bold leading-none">
                      {detail.latest.close.toFixed(2)}
                      <span className={`ml-2 text-sm align-middle ${retColor(detail.latest.change_percent)}`}>
                        {retText(detail.latest.change_percent)}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1.5">当日 {detail.latest.date}</div>
                  </div>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">开</span>
                      <span className="font-medium">{detail.latest.open.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">高</span>
                      <span className="font-medium text-red-600">{detail.latest.high.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">低</span>
                      <span className="font-medium text-green-600">{detail.latest.low.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">昨收</span>
                      <span className="font-medium">{detail.latest.close.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">量</span>
                      <span className="font-medium">{fmtVolume(detail.latest.volume)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">额</span>
                      <span className="font-medium">{fmtVolume(detail.latest.amount)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-gray-400">换手</span>
                      <span className="font-medium">{detail.latest.turnover_rate.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="border border-gray-100 rounded-xl p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <span className="w-1 h-3.5 rounded bg-violet-500" />
                  <span className="text-xs text-gray-500 font-medium">区间收益</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(detail.period_returns).map(([k, v]) => (
                    <div
                      key={k}
                      className={`px-2.5 py-1.5 rounded-md text-center min-w-[74px] ${
                        v === null
                          ? 'bg-gray-50'
                          : v >= 0
                            ? 'bg-red-50'
                            : 'bg-green-50'
                      }`}
                    >
                      <div className={`text-sm font-bold ${retColor(v)}`}>{retText(v)}</div>
                      <div className="text-[11px] text-gray-400 mt-0.5">{k}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 资产情况 (市值/股本/估值) */}
            <div className="border border-gray-100 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-1.5 mb-3">
                <span className="w-1 h-3.5 rounded bg-violet-500" />
                <span className="text-xs text-gray-500 font-medium">资产情况</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-4">
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">总市值</span>
                  <span className="text-sm font-semibold">{detail.asset.total_market_value != null ? `${fmtNum(detail.asset.total_market_value)}亿` : '—'}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">流通市值</span>
                  <span className="text-sm font-semibold">{detail.asset.float_market_value != null ? `${fmtNum(detail.asset.float_market_value)}亿` : '—'}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">总股本</span>
                  <span className="text-sm font-semibold">{detail.asset.total_shares != null ? `${fmtNum(detail.asset.total_shares)}亿股` : '—'}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">流通股本</span>
                  <span className="text-sm font-semibold">{detail.asset.float_shares != null ? `${fmtNum(detail.asset.float_shares)}亿股` : '—'}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">市盈率 PE</span>
                  <span className="text-sm font-semibold">{fmtNum(detail.asset.pe)}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">市净率 PB</span>
                  <span className="text-sm font-semibold">{fmtNum(detail.asset.pb)}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">量比</span>
                  <span className="text-sm font-semibold">{fmtNum(detail.asset.volume_ratio)}</span>
                </div>
                <div className="flex items-baseline justify-between border-b border-gray-50 pb-2">
                  <span className="text-xs text-gray-400">换手率</span>
                  <span className="text-sm font-semibold">{detail.asset.turnover_rate != null ? `${fmtNum(detail.asset.turnover_rate)}%` : '—'}</span>
                </div>
              </div>
              {detail.asset.code == null && (
                <div className="text-xs text-gray-400 mt-2">该股票暂无资产快照数据（可在「信号扫描 → 刷新资产快照」更新）</div>
              )}
            </div>

            {/* 技术指标 */}
            <div>
              <IndicatorGuide
                title="指标说明"
                items={[
                  { term: 'MA5/10/20/60', desc: '5/10/20/60日均线。股价在均线上方偏强，短期线在长期线上方为多头排列。(K线图中同色曲线)' },
                  { term: 'MACD', desc: '基于两条均线差研判趋势；MACD柱为正(红)偏多、为负(绿)偏空；白线(DIF)上穿黄线(DEA)为金叉买入信号' },
                  { term: 'RSI', desc: '0-100涨跌力量比，>70超买小心回调、<30超卖可能反弹' },
                  { term: 'KDJ', desc: '短期摆动指标，K/D值>80超买、<20超卖，金叉/死叉参考短线买卖' },
                  { term: '布林(BOLL) 上中下轨', desc: '价格通道三轨，触及上轨偏超买、触及下轨偏超卖，通道收窄预示变盘' },
                  { term: 'ATR 真实波幅', desc: '衡量单日波动幅度大小，值越大波动越剧烈，常用于设止损幅度' },
                  { term: '换手率', desc: '当日成交量/流通股本，越高交投越活跃' },
                ]}
              />
              <div className="flex items-center gap-1.5 mb-2">
                <span className="w-1 h-3.5 rounded bg-violet-500" />
                <span className="text-xs text-gray-500 font-medium">技术指标</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {indicators.map((it, i) => (
                  <div key={i} className="p-2 bg-gray-50 rounded text-center">
                    <div className="text-[11px] text-gray-400">{it.label}</div>
                    <div className="text-sm font-medium">{it.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* K 线图 */}
            <div className="mt-4">
              <div className="flex items-center gap-1 mb-2 flex-wrap">
                <span className="text-xs text-gray-500 mr-1">K线范围:</span>
                {timeRanges.map((r) => (
                  <button
                    key={r.key}
                    onClick={() => setRange(r.key)}
                    disabled={loading}
                    className={`px-2.5 py-1 text-xs rounded-md border ${
                      range === r.key
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'border-gray-200 hover:bg-gray-50 disabled:opacity-50'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <div className="h-[400px]">
                <ReactECharts option={option} style={{ height: '100%' }} notMerge />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}