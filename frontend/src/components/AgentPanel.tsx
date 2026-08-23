import { FC, useState, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import { marked } from 'marked'
import type { AgentChatResult } from '@/types'
import { api, getWebChatToken, setWebChatToken } from '@/services/api'
import { IndicatorGuide } from './IndicatorGuide'

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  result?: AgentChatResult
  error?: string
}

// 字段名 -> 中文表头
const COLUMN_LABELS: Record<string, string> = {
  code: '代码', name: '名称', pinyin: '拼音', date: '日期',
  open: '开盘', close: '收盘', high: '最高', low: '最低',
  volume: '成交量', amount: '成交额', amplitude: '振幅%',
  change_percent: '涨跌幅%', pct_change: '区间涨幅%', turnover_rate: '换手率%',
  ma5: 'MA5', ma10: 'MA10', ma20: 'MA20', ma60: 'MA60',
  ema12: 'EMA12', ema26: 'EMA26',
  macd: 'DIF', macd_signal: 'DEA', macd_hist: 'MACD柱',
  rsi: 'RSI', boll_mid: '布林中轨', boll_upper: '布林上轨', boll_lower: '布林下轨',
  kdj_k: 'KDJ-K', kdj_d: 'KDJ-D', kdj_j: 'KDJ-J', atr: 'ATR',
  momentum_5d: '5日动量%', momentum_10d: '10日动量%', momentum_20d: '20日动量%',
  volatility_5d: '5日波动率', volatility_10d: '10日波动率', volatility_20d: '20日波动率',
  close_ma5_ratio: '收盘/MA5偏离%', close_ma20_ratio: '收盘/MA20偏离%', close_ma60_ratio: '收盘/MA60偏离%',
  macd_cross: 'MACD金叉', rsi_oversold: 'RSI超卖', rsi_overbought: 'RSI超买',
  boll_position: '布林位置', boll_width: '布林宽度', kdj_cross: 'KDJ金叉', obv_signal: 'OBV信号',
  ma_cross: '均线交叉', trend: '趋势', direction: '方向',
  atr_ratio: 'ATR/收盘', obv: '能量潮', obv_ma10: 'OBV-MA10',
  williams_r: '威廉R', williams_overbought: '威廉超买', williams_oversold: '威廉超卖',
  roc_10: '10日变动率%', roc_20: '20日变动率%',
  change_amount: '涨跌额', high_low_ratio: '最高/最低比', close_open_ratio: '收盘/开盘比',
  upper_shadow: '上影线长', lower_shadow: '下影线长', body_size: 'K线实体长度',
}

const colLabel = (c: string): string => COLUMN_LABELS[c] ?? c

// 大数值字段 -> 换万单位的表头标注 (volume=手→万手, amount=元→万元)
const WAN_UNIT: Record<string, string> = {
  volume: '万手',
  amount: '万元',
}
const colLabelWithUnit = (c: string): string => {
  const unit = WAN_UNIT[c]
  return unit ? `${colLabel(c)}(${unit})` : colLabel(c)
}
// 大数值字段换算: 原始值/10000
const convertWan = (c: string, n: number): number => (c in WAN_UNIT ? n / 10000 : n)

// AI 回答体统一走 markdown 渲染
const renderMarkdown = (text: string): string => marked.parse(text, { async: false }) as string

const SUGGESTIONS: { label: string; text: string }[] = [
  { label: '今日涨幅 TOP10', text: '今天涨幅最大的 10 只股票有哪些？' },
  { label: '茅台技术面', text: '贵州茅台最近走势如何，技术面偏多还是偏空？' },
  { label: 'RSI 超买股', text: '当前 RSI 超买(>70)的股票有哪些？' },
  { label: '我的持仓', text: '我的持仓现在表现如何，哪些建议减仓？' },
]

// 回答后的追问建议(可点击直接发送)
const FOLLOWUPS: { label: string; text: string }[] = [
  { label: '看 K 线趋势', text: '这些股票的 K 线走势如何，趋势是偏多还是偏空？' },
  { label: '涨幅 TOP10', text: '今天涨幅最大的 10 只股票有哪些？' },
  { label: '分析我的持仓', text: '我的持仓现在表现如何，哪些建议减仓？' },
]

const trim = (v: unknown, digits = 3): number | null => {
  if (v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? +n.toFixed(digits) : null
}

// 红涨绿跌
const valCls = (v: number | null): string => {
  if (v === null || v === 0) return 'text-gray-600'
  return v > 0 ? 'text-red-600' : 'text-green-600'
}

// 0/1 -1 标记字段: 表示「是/否/金叉/死叉」等状态, 非数值涨跌, 不能用红绿配色
const BOOL_FIELDS = new Set([
  'macd_cross', 'rsi_overbought', 'rsi_oversold', 'kdj_cross',
  'obv_signal', 'ma_cross', 'williams_overbought', 'williams_oversold',
])
// 标记字段 -> 值 -> 语义文案 (-1/0/1 及任意非零)
const BOOL_LABELS: Record<string, Record<number, string>> = {
  macd_cross: { 1: '金叉', '-1': '死叉', 0: '无' },
  kdj_cross: { 1: '金叉', '-1': '死叉', 0: '无' },
  ma_cross: { 1: '金叉', '-1': '死叉', 0: '无' },
  rsi_overbought: { 1: '超买', 0: '' },
  rsi_oversold: { 1: '超卖', 0: '' },
  williams_overbought: { 1: '超买', 0: '' },
  williams_oversold: { 1: '超卖', 0: '' },
  obv_signal: { 1: '金叉', '-1': '死叉', 0: '无' },
}

export const AgentPanel: FC = () => {
  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showSql, setShowSql] = useState(false)
  const [showToken, setShowToken] = useState(false)
  const [token, setToken] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, sending])

  // 初始化令牌(来自 localStorage), 并同步给 api 层
  useEffect(() => {
    const saved = getWebChatToken()
    setToken(saved)
  }, [])

  const send = async (text?: string) => {
    const q = (text ?? input).trim()
    if (!q || sending) return
    setInput('')
    const userMsg: ChatMsg = { role: 'user', content: q }
    const assMsg: ChatMsg = { role: 'assistant', content: '', error: '', result: undefined }
    setMsgs((m) => [...m, userMsg, assMsg])
    setSending(true)
    try {
      const history = msgs
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))
      const res = await api.agentChat([...history.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })), { role: 'user', content: q }])
      setMsgs((m) => {
        const arr = [...m]
        arr[arr.length - 1] = res.success
          ? { ...arr[arr.length - 1], content: res.answer ?? res.message ?? '', result: res }
          : { ...arr[arr.length - 1], error: res.message ?? '查询失败' }
        return arr
      })
    } catch (e) {
      setMsgs((m) => {
        const arr = [...m]
        arr[arr.length - 1] = { ...arr[arr.length - 1], error: (e as Error).message }
        return arr
      })
    } finally {
      setSending(false)
    }
  }

  const renderChart = (chart: NonNullable<AgentChatResult['chart']>, rows: Record<string, unknown>[]) => {
    const ds = chart.dataset?.length ? chart.dataset : rows
    if (!ds.length) return null
    const xField = chart.x ?? 'code'
    const yField = (chart.y ?? [])[0] ?? 'value'
    const xData = ds.map((r) => String(r[xField] ?? ''))
    const yData = ds.map((r) => trim(r[yField]))

    const colors = ['#ef4444', '#f97316', '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#14b8a6', '#ec4899']
    let option: Record<string, unknown>
    const axisCommon = {
      xAxis: { type: 'category', data: xData, axisLabel: { rotate: xData.length > 8 ? 40 : 0 } },
      yAxis: { type: 'value' },
      tooltip: { trigger: 'axis' as const },
      title: { text: chart.title ?? '', left: 'center', textStyle: { fontSize: 13 } },
    }
    if (chart.type === 'line') {
      option = {
        ...axisCommon,
        series: [
          {
            type: 'line',
            data: yData,
            smooth: true,
            itemStyle: { color: '#ef4444' },
            lineStyle: { color: '#ef4444' },
          },
        ],
      }
    } else if (chart.type === 'pie') {
      option = {
        ...axisCommon,
        xAxis: undefined,
        yAxis: undefined,
        series: [
          {
            type: 'pie',
            radius: ['40%', '68%'],
            label: { fontSize: 11 },
            itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
            data: ds.map((r, i) => ({ name: String(r[xField]), value: trim(r[yField]) ?? 0, itemStyle: { color: colors[i % colors.length] } })),
          },
        ],
        legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
      }
    } else {
      option = {
        ...axisCommon,
        series: [
          {
            type: 'bar',
            data: yData.map((v, i) => ({ value: v, itemStyle: { color: v != null && v < 0 ? '#22c55e' : colors[i % colors.length] } })),
          },
        ],
      }
    }
    return (
      <div className="mt-3 h-64 border rounded-md p-2 bg-white">
        <ReactECharts option={option} style={{ width: '100%', height: '100%' }} notMerge />
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm flex flex-col">
      <div className="mb-1">
        <h2 className="text-xl font-semibold">🤖 AI 选股助手</h2>
        <p className="text-gray-500 text-sm">
          用自然语言问股票行情、指标、选股、持仓诊断。系统把问题转成只读 SQL 查真实数据后作答。
        </p>
      </div>

      <IndicatorGuide
        title="怎么用"
        items={[
          { term: '问行情', desc: '如“今天涨幅最大的10只股票”“贵州茅台最近走势”' },
          { term: '问指标', desc: '支持 MA/MACD/RSI/KDJ/BOLL/换手率等技术面筛选，如“RSI超买股”' },
          { term: '问持仓', desc: '结合“模拟仓”自动分析，如“我的持仓现在如何，哪些该减仓”' },
          { term: '数据安全', desc: 'Agent 只能生成只读 SELECT查询，绝不改写任何数据；持仓与查询结果会随问题发送至所配置的第三方LLM服务，请留意其数据使用条款' },
        ]}
      />

      {/* 访问令牌(可选): 仅当部署方开启了 WEB_CHAT_TOKEN 鉴权时才需要填; 公开 Demo 留空即可 */}
      <div className="mt-3 text-xs">
        <button
          type="button"
          onClick={() => setShowToken((s) => !s)}
          className="text-gray-500 hover:text-blue-600 underline-offset-2 hover:underline"
        >
          {showToken ? '收起访问令牌' : '设置访问令牌（可选）'}
        </button>
        {showToken && (
          <div className="mt-2 flex gap-2 items-center">
            <input
              type={token ? 'password' : 'text'}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              onBlur={() => setWebChatToken(token.trim())}
              placeholder="私有部署请填后端 WEB_CHAT_TOKEN；公开 Demo 不用填"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                setToken('')
                setWebChatToken('')
              }}
              className="px-2 py-1.5 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 text-xs"
            >
              清除
            </button>
          </div>
        )}
        {showToken && token.trim() && (
          <p className="mt-1 text-green-600">✓ 已保存，发送问题时会带上 Bearer 令牌</p>
        )}
      </div>

      {/* 消息区 */}
      <div className="mt-3 space-y-4">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.text}
                onClick={() => send(s.text)}
                className="text-sm border border-gray-200 rounded-full px-3 py-1 hover:bg-blue-50 hover:border-blue-300"
              >
                {s.label}
              </button>
            ))}
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                m.role === 'user'
                  ? 'max-w-[80%] bg-blue-600 text-white rounded-xl px-3 py-2 text-sm'
                  : 'max-w-[92%] text-sm space-y-2'
              }
            >
              {m.role === 'user' ? (
                m.content
              ) : m.error ? (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2">❌ {m.error}</div>
              ) : (
                (() => {
                  const r = m.result
                  const rows = r?.rows ?? []
                  const cols = r?.columns ?? []
                  return (
                    <>
                      <div className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                        ⚠️ 演示数据：以下为 Demo 模拟行情（股票名称已脱敏为 DemoXX），非实时市场数据，数据日期以查询结果中的日期为准。
                      </div>
                      {m.content && <div className="md-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />}
                      {r?.chart && renderChart(r.chart, rows)}
                      {r && rows.length > 0 && (
                        <div className="border border-gray-100 rounded-md overflow-hidden">
                          <div className="overflow-x-auto">
                            <table className="text-xs min-w-max">
                              <thead className="bg-gray-50 sticky top-0">
                                <tr>
                                  {cols.map((c) => (
                                    <th key={c} className="px-3 py-1.5 text-left font-medium border-b whitespace-nowrap">{colLabelWithUnit(c)}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {rows.map((row, ri) => (
                                  <tr key={ri} className={`${ri % 2 ? 'bg-gray-50' : ''} hover:bg-blue-50`}>
                                    {cols.map((c) => {
                                      const raw = row[c]
                                      const isNum = typeof raw === 'number' || (typeof raw === 'string' && raw !== '' && !Number.isNaN(Number(raw)) && /(c|chg|pct|ret|rsi|ratio|turnover|momentum|roc|vol)\s*$/i.test(String(c)))
                                      const n = convertWan(c, trim(raw, 2) ?? NaN) // 成交量/成交额换算为万
                                      const isBool = BOOL_FIELDS.has(c)
                                      const boolText = isBool && raw !== null && raw !== undefined
                                        ? (BOOL_LABELS[c]?.[Number(raw)] ?? String(raw))
                                        : ''
                                      const text = raw === null || raw === undefined
                                        ? '—'
                                        : isBool
                                          ? (boolText || '—')
                                          : isNum && Number.isFinite(n)
                                            ? n.toFixed(2) // 保留两位小数
                                            : String(raw)
                                      const cellCls = isBool
                                        ? 'font-mono text-gray-600' // 标记字段中性色
                                        : isNum
                                          ? `font-mono ${valCls(n)}`
                                          : 'whitespace-nowrap'
                                      return (
                                        <td key={c} className={`px-3 py-1.5 border-b ${cellCls}`}>
                                          {text}
                                        </td>
                                      )
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="text-[11px] text-gray-400 px-2 py-1 bg-gray-50 border-t">
                            共 {r.row_count} 行{r.truncated ? '（已截断）' : ''} | SQL：
                            <button className="ml-1 text-blue-600 hover:underline" onClick={() => setShowSql((s) => !s)}>
                              {showSql ? '收起' : '查看'}
                            </button>
                          </div>
                          {showSql && r.sql && (
                            <pre className="text-[11px] bg-gray-900 text-gray-100 px-3 py-2 overflow-x-auto whitespace-pre-wrap">{r.sql}</pre>
                          )}
                        </div>
                      )}
                      {/* 回答后的追问建议: 优先用 AI 动态生成, 空则回退静态 */}
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {r?.followups?.length ? (
                          r.followups.map((q, fi) => (
                            <button
                              key={`${fi}-${q}`}
                              onClick={() => send(q)}
                              className="text-xs text-blue-600 border border-blue-200 rounded-full px-2.5 py-0.5 hover:bg-blue-50 hover:border-blue-300"
                            >
                              {q}
                            </button>
                          ))
                        ) : (
                          FOLLOWUPS.map((f) => (
                            <button
                              key={f.text}
                              onClick={() => send(f.text)}
                              className="text-xs text-blue-600 border border-blue-200 rounded-full px-2.5 py-0.5 hover:bg-blue-50 hover:border-blue-300"
                            >
                              {f.label}
                            </button>
                          ))
                        )}
                      </div>
                    </>
                  )
                })()
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="text-sm text-gray-400">
              AI 正在查询并分析...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="mt-3 flex gap-2 border-t pt-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="输入问题，如：今天涨跌结构如何？帮我分析持仓..."
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={() => send()}
          disabled={sending || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          发送
        </button>
      </div>
    </div>
  )
}