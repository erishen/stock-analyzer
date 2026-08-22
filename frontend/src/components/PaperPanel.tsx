import { FC, useState, useEffect } from 'react'
import type { PaperResult, PaperPosition } from '@/types'
import { api } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'
import { StockDetailModal } from './StockDetailModal'

// 涨幅<->颜色: 红=涨 绿=跌
const pnlCls = (v: number): string =>
  v > 0 ? 'text-red-600' : v < 0 ? 'text-green-600' : 'text-gray-600'

// 诊断级别 -> 标签样式
const levelStyle: Record<string, string> = {
  danger: 'bg-red-100 text-red-700 border-red-200',
  warning: 'bg-amber-100 text-amber-700 border-amber-200',
  success: 'bg-green-100 text-green-700 border-green-200',
  info: 'bg-blue-100 text-blue-700 border-blue-200',
  muted: 'bg-gray-100 text-gray-600 border-gray-200',
}

const fmt = (v: number | null | undefined, digits = 2): string =>
  v === null || v === undefined ? '—' : v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })

const today = () => new Date().toISOString().slice(0, 10)

// 大盘市场状态: 英文枚举 -> 中文
const marketStateText: Record<string, string> = {
  bull: '牛市',
  bear: '熊市',
  sideways: '震荡市',
}

export const PaperPanel: FC = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [result, setResult] = useState<PaperResult | null>(null)

  // 建仓表单
  const [code, setCode] = useState('')
  const [buyPrice, setBuyPrice] = useState('')
  const [shares, setShares] = useState('')
  const [buyDate, setBuyDate] = useState(today())
  const [stopLoss, setStopLoss] = useState('8')
  const [takeProfit, setTakeProfit] = useState('20')

  // 卖出表单
  const [sellTarget, setSellTarget] = useState<PaperPosition | null>(null)
  const [sellPrice, setSellPrice] = useState('')
  const [sellDate, setSellDate] = useState(today())

  // 个股详情弹窗
  const [detailCode, setDetailCode] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setResult(await api.getPaper())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const showFlash = (m: string) => {
    setFlash(m)
    setTimeout(() => setFlash(''), 3000)
  }

  const handleAdd = async () => {
    setError('')
    if (!code.trim() || !buyPrice || !shares) {
      setError('请填写股票代码、买入价、股数')
      return
    }
    try {
      const r = await api.addPaperPosition({
        code: code.trim(),
        buy_price: Number(buyPrice),
        shares: Number(shares),
        buy_date: buyDate,
        stop_loss: Number(stopLoss) / 100,
        take_profit: Number(takeProfit) / 100,
      })
      if (!r.success) { setError(r.message); return }
      showFlash(r.message)
      setCode(''); setBuyPrice(''); setShares('')
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const openSell = (p: PaperPosition) => {
    setSellTarget(p)
    setSellPrice(p.current_price ? String(p.current_price) : '')
    setSellDate(today())
  }

  const handleSell = async () => {
    if (!sellTarget || !sellPrice) return
    setError('')
    try {
      const r = await api.closePaperPosition({
        code: sellTarget.code,
        sell_price: Number(sellPrice),
        sell_date: sellDate,
      })
      if (!r.success) { setError(r.message); setSellTarget(null); return }
      showFlash(r.message)
      setSellTarget(null)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const s = result?.summary

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">📒 模拟仓</h2>
      <p className="text-gray-500 text-sm mb-4">
        记录你的模拟买入，系统结合实时行情与指标，对每只持仓和整体组合给出「持有/减仓/止盈/止损」诊断
      </p>

      <IndicatorGuide
        items={[
          { term: '买入价+股数', desc: '记录你的建仓成本，用于计算盈亏额与收益率' },
          { term: '止损/止盈', desc: '给每只股票定离场线：跌破止损线建议止损；达到止盈线建议锁定收益（红涨绿跌）' },
          { term: '诊断级别', desc: '红色=止损或偏空(建议离场)、橙色=转弱(建议关注/减仓)、绿色=达到止盈(锁定)、蓝色=正常持有' },
          { term: '大盘环境', desc: '顶部引用「大盘择时」的仓位建议，大环境转弱时整体降仓' },
          { term: '集中度', desc: '单只股票市值占总市值比例，越高风险越集中，建议分散' },
        ]}
      />

      {/* 大盘环境 */}
      {result?.market && (result.market.state || result.market.advice) && (
        <div className="mb-5 p-3 rounded-md bg-indigo-50 border border-indigo-100 text-sm">
          <span className="font-semibold text-indigo-800">大盘：{marketStateText[result.market.state] || result.market.state || '—'}</span>
          <span className="text-indigo-700 ml-2">{result.market.advice}</span>
        </div>
      )}

      {/* 组合概览 */}
      {s && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-5">
          {[
            { label: '持仓数', value: `${s.position_count} 只` },
            { label: '总成本', value: fmt(s.total_cost, 0) },
            { label: '总市值', value: fmt(s.total_value, 0) },
            { label: '总盈亏额', value: `${s.total_pnl >= 0 ? '+' : ''}${fmt(s.total_pnl, 0)}`, color: pnlCls(s.total_pnl) },
            { label: '总盈亏率', value: `${s.total_pnl_pct >= 0 ? '+' : ''}${fmt(s.total_pnl_pct)}%`, color: pnlCls(s.total_pnl_pct) },
            { label: '单票最大占比', value: `${fmt(s.max_weight)}%`, color: s.max_weight > 30 ? 'text-amber-600' : '' },
          ].map((item, i) => (
            <div key={i} className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500 mb-1">{item.label}</div>
              <div className={`text-lg font-semibold ${item.color || ''}`}>{item.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* 建仓表单 */}
      <div className="grid grid-cols-2 md:grid-cols-7 gap-3 items-end mb-4 bg-gray-50 p-4 rounded-md">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">股票代码</label>
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="如 600519"
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">买入价</label>
          <input type="number" value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)}
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">股数</label>
          <input type="number" value={shares} onChange={(e) => setShares(e.target.value)}
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">买入日期</label>
          <input type="date" value={buyDate} onChange={(e) => setBuyDate(e.target.value)}
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">止损%</label>
          <input type="number" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)}
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">止盈%</label>
          <input type="number" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)}
            className="p-2 border border-gray-200 rounded-md bg-white" />
        </div>
        <button onClick={handleAdd} disabled={loading}
          className="px-4 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50 h-[42px]">
          建仓
        </button>
      </div>

      {flash && <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-md text-sm">{flash}</div>}
      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}

      {loading && <div className="py-4 text-gray-400 text-sm">加载中...</div>}

      {/* 持仓列表 */}
      {!loading && result && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">当前持仓</h3>
            <button onClick={() => load()} className="text-xs text-violet-600 hover:underline">
              刷新行情
            </button>
          </div>

          {result.positions.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm border border-dashed border-gray-200 rounded-md">
              还没有持仓。在上方填入代码、买入价、股数点「建仓」，系统即可开始诊断。
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    {['代码', '买入日', '买入价', '现价', '今涨跌', '市值', '盈亏额', '盈亏率', '占比', '诊断', '操作'].map((h) => (
                      <th key={h} className="p-2 text-left text-xs font-semibold text-gray-500 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.positions.map((p) => (
                    <tr key={p.code} className="border-b border-gray-100 align-top">
                      <td className="p-2">
                        <button
                          onClick={() => setDetailCode(p.code)}
                          className="text-violet-600 hover:underline font-medium">{p.code}</button>
                        <div className="text-xs text-gray-400">{p.name}</div>
                      </td>
                      <td className="p-2 whitespace-nowrap">{p.buy_date}</td>
                      <td className="p-2 whitespace-nowrap">{fmt(p.buy_price)}</td>
                      <td className="p-2 whitespace-nowrap">{p.current_price === null ? '—' : fmt(p.current_price)}</td>
                      <td className={`p-2 whitespace-nowrap ${pnlCls(p.change_percent)}`}>{p.change_percent >= 0 ? '+' : ''}{fmt(p.change_percent)}%</td>
                      <td className="p-2 whitespace-nowrap">{fmt(p.value, 0)}</td>
                      <td className={`p-2 whitespace-nowrap ${pnlCls(p.pnl)}`}>{p.pnl >= 0 ? '+' : ''}{fmt(p.pnl, 0)}</td>
                      <td className={`p-2 whitespace-nowrap font-medium ${pnlCls(p.pnl_pct)}`}>{p.pnl_pct >= 0 ? '+' : ''}{fmt(p.pnl_pct)}%</td>
                      <td className="p-2 whitespace-nowrap">{fmt(p.weight)}%</td>
                      <td className="p-2 min-w-[200px]">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${levelStyle[p.level] || ''}`}>{p.action}</span>
                          <span className="text-xs text-gray-400">止损{Math.round(p.stop_loss * 100)}% / 止盈{Math.round(p.take_profit * 100)}%</span>
                        </div>
                        <div className="text-xs text-gray-600">{p.advice}</div>
                      </td>
                      <td className="p-2 whitespace-nowrap">
                        <button onClick={() => openSell(p)}
                          className="px-3 py-1 rounded text-xs bg-gray-200 text-gray-700 hover:bg-gray-300">
                          卖出
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 卖出弹窗 */}
      {sellTarget && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setSellTarget(null)}>
          <div className="bg-white rounded-lg p-5 w-80 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">卖出 {sellTarget.name} ({sellTarget.code})</h3>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col">
                <label className="text-xs text-gray-500 mb-1">卖出价</label>
                <input type="number" value={sellPrice} onChange={(e) => setSellPrice(e.target.value)}
                  className="p-2 border border-gray-200 rounded-md" />
              </div>
              <div className="flex flex-col">
                <label className="text-xs text-gray-500 mb-1">卖出日期</label>
                <input type="date" value={sellDate} onChange={(e) => setSellDate(e.target.value)}
                  className="p-2 border border-gray-200 rounded-md" />
              </div>
              <div className="text-xs text-gray-500">
                持仓 {fmt(sellTarget.shares, 0)} 股，成本 {fmt(sellTarget.buy_price)}，现价 {sellTarget.current_price === null ? '—' : fmt(sellTarget.current_price)}
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setSellTarget(null)} className="px-3 py-1.5 rounded bg-gray-200 text-gray-700">取消</button>
                <button onClick={handleSell} className="px-3 py-1.5 rounded bg-violet-600 text-white hover:bg-violet-700">确认卖出</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 卖出历史 */}
      {result && result.closed.length > 0 && (
        <div>
          <h3 className="font-semibold mb-3">卖出历史</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-gray-50">
                  {['代码', '卖出日', '买入价', '卖出价', '股数', '盈亏额', '盈亏率'].map((h) => (
                    <th key={h} className="p-2 text-left text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.closed.map((c, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="p-2">
                      <button onClick={() => setDetailCode(c.code)}
                        className="text-violet-600 hover:underline font-medium">{c.code}</button>
                      <span className="text-xs text-gray-400 ml-1">{c.name}</span>
                    </td>
                    <td className="p-2">{c.sell_date}</td>
                    <td className="p-2">{fmt(c.buy_price)}</td>
                    <td className="p-2">{fmt(c.sell_price)}</td>
                    <td className="p-2">{fmt(c.shares, 0)}</td>
                    <td className={`p-2 ${pnlCls(c.profit)}`}>{c.profit >= 0 ? '+' : ''}{fmt(c.profit, 0)}</td>
                    <td className={`p-2 font-medium ${pnlCls(c.profit_pct * 100)}`}>{c.profit_pct * 100 >= 0 ? '+' : ''}{fmt(c.profit_pct * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {detailCode && <StockDetailModal code={detailCode} onClose={() => setDetailCode(null)} />}
    </div>
  )
}