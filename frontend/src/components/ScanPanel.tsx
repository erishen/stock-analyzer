import { FC, useState, useEffect } from 'react'
import type { ScanResult, Signal } from '@/types'
import { api } from '@/services/api'
import { StockDetailModal } from './StockDetailModal'
import { IndicatorGuide } from './IndicatorGuide'
import { ScreenerPanel } from './ScreenerPanel'

const signalTypes = [
  { value: '', label: '全部信号' },
  { value: 'macd_golden_cross', label: 'MACD金叉' },
  { value: 'macd_dead_cross', label: 'MACD死叉' },
  { value: 'kdj_golden_cross', label: 'KDJ金叉' },
  { value: 'rsi_oversold', label: 'RSI超卖' },
  { value: 'rsi_overbought', label: 'RSI超买' },
  { value: 'boll_lower', label: '触及布林下轨' },
  { value: 'boll_upper', label: '触及布林上轨' },
  { value: 'trend_up', label: '上升趋势' },
  { value: 'trend_down', label: '下降趋势' },
]

const getStrengthColor = (strength: string): string => {
  switch (strength) {
    case '强': return 'bg-green-100 text-green-800'
    case '弱': return 'bg-yellow-100 text-yellow-800'
    default: return 'bg-purple-100 text-purple-800'
  }
}

// 信号类型 id → 中文名 (与下拉选项一致)
const signalLabel = (t: string): string =>
  signalTypes.find((x) => x.value === t)?.label ?? t

export const ScanPanel: FC = () => {
  const [view, setView] = useState<'scan' | 'screener'>('scan')
  const [signalType, setSignalType] = useState('')
  const [minScore, setMinScore] = useState(60)
  const [limit, setLimit] = useState(50)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)

  const handleScan = async (refresh = false) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.scanSignals({
        signal_type: signalType || undefined,
        min_score: minScore,
        limit: limit,
        refresh: refresh,
      })
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  // 挂载时自动加载缓存结果 (面板常驻, 首算可能耗时, 之后瞬显)
  useEffect(() => {
    handleScan(false)
  }, [])

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <div className="flex gap-1 mb-3 bg-gray-50 p-1 rounded-lg w-fit">
        <button
          onClick={() => setView('scan')}
          className={`px-5 py-1.5 rounded-md text-sm transition-all ${
            view === 'scan' ? 'bg-violet-600 text-white' : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          信号扫描
        </button>
        <button
          onClick={() => setView('screener')}
          className={`px-5 py-1.5 rounded-md text-sm transition-all ${
            view === 'screener' ? 'bg-violet-600 text-white' : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          自定义规则
        </button>
      </div>

      {view === 'screener' ? (
        <ScreenerPanel />
      ) : (
      <>
      <h2 className="text-xl font-semibold mb-1">信号扫描</h2>
      <p className="text-gray-500 text-sm mb-4">扫描全市场技术信号，发现交易机会</p>

      <IndicatorGuide
        items={[
          { term: 'MACD金叉/死叉', desc: 'MACD快速线向上/向下穿越慢速线，金叉看涨、死叉看跌' },
          { term: 'KDJ金叉', desc: 'KDJ在低位向上交叉，往往预示短期反弹机会' },
          { term: 'RSI超买/超卖', desc: 'RSI过高(超买)易回调、过低(超卖)易反弹' },
          { term: '触及布林带', desc: '价格触及布林上轨(偏强)或下轨(偏弱)，关注方向选择' },
          { term: '上升/下降趋势', desc: '价格均线的持续上行/下行结构，代表中长期方向' },
          { term: '强度', desc: '信号确认力度：强=多信号共振更可靠，弱=需谨慎对待' },
          { term: '得分', desc: '0-100 的综合评分，越高代表该股票信号质量越好' },
        ]}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">信号类型</label>
          <select
            value={signalType}
            onChange={(e) => setSignalType(e.target.value)}
            className="p-2 border border-gray-200 rounded-md"
          >
            {signalTypes.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">最低得分</label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">显示数量</label>
          <input
            type="number"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => handleScan(false)}
          disabled={loading}
          className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? '扫描中...' : '开始扫描'}
        </button>
        {result && result.success && (
          <button
            onClick={() => handleScan(true)}
            disabled={loading}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
          >
            重新扫描
          </button>
        )}
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div className="mt-5">
          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500 mb-1">扫描股票</div>
              <div className="text-xl font-semibold">{result.total_stocks.toLocaleString()}</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500 mb-1">发现信号</div>
              <div className="text-xl font-semibold">{result.signals_found.toLocaleString()}</div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">代码</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">名称</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">信号类型</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">强度</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">得分</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">价格</th>
                  <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                {result.signals.map((s: Signal, i: number) => (
                  <tr key={i} className="hover:bg-gray-50 border-b border-gray-100">
                    <td className="p-3 text-sm">
                      <button
                        onClick={() => setSelectedCode(s.code)}
                        className="text-violet-600 hover:underline cursor-pointer"
                      >
                        {s.code}
                      </button>
                    </td>
                    <td className="p-3 text-sm">
                      <button
                        onClick={() => setSelectedCode(s.code)}
                        className="hover:text-violet-600 cursor-pointer"
                      >
                        {s.name}
                      </button>
                    </td>
                    <td className="p-3">
                      <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800">
                        {signalLabel(s.signal_type)}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-1 text-xs rounded ${getStrengthColor(s.strength)}`}>
                        {s.strength}
                      </span>
                    </td>
                    <td className="p-3 text-sm">{s.score.toFixed(1)}</td>
                    <td className="p-3 text-sm">{s.price.toFixed(2)}</td>
                    <td className={`p-3 text-sm ${s.change_percent >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {s.change_percent >= 0 ? '+' : ''}{s.change_percent.toFixed(2)}%
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
      </>
      )}
    </div>
  )
}
