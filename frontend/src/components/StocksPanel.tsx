import { FC, useState, useEffect, useRef } from 'react'
import type { StockRow, StocksPageResult, UpdateStatus } from '@/types'
import { api } from '@/services/api'
import { StockDetailModal } from '@/components/StockDetailModal'
import { IndicatorGuide } from '@/components/IndicatorGuide'

// 数值格式化: 成交量(股)→万/亿手, 成交额(元)→万/亿
const fmtVolume = (v: number): string => {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return String(v)
}

const fmtAmount = (v: number): string => {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return String(v)
}

const maxPageButtons = 7

// 市场筛选选项 (值与后端 MARKET_FILTERS 对应)
const marketOptions = [
  { value: '', label: '全部市场' },
  { value: 'sh', label: '上交所 (主板+科创)' },
  { value: 'sz', label: '深交所 (主板+创业)' },
  { value: 'sh_main', label: '上证主板' },
  { value: 'star', label: '科创板' },
  { value: 'sz_main', label: '深证主板' },
  { value: 'chinext', label: '创业板' },
  { value: 'bj', label: '北交所' },
]

// 市场标签配色
const getMarketColor = (m: string): string => {
  switch (m) {
    case '上证主板': return 'bg-blue-100 text-blue-800'
    case '科创板': return 'bg-purple-100 text-purple-800'
    case '深证主板': return 'bg-emerald-100 text-emerald-800'
    case '创业板': return 'bg-orange-100 text-orange-800'
    case '北交所': return 'bg-cyan-100 text-cyan-800'
    default: return 'bg-gray-100 text-gray-600'
  }
}

export const StocksPanel: FC = () => {
  const [search, setSearch] = useState('')
  const [date, setDate] = useState('')
  const [market, setMarket] = useState('')
  const [sortBy, setSortBy] = useState('code')
  const [sortOrder, setSortOrder] = useState('asc')
  const [pageSize, setPageSize] = useState(50)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<StocksPageResult | null>(null)
  const [error, setError] = useState('')
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null)
  const [updateEnabled, setUpdateEnabled] = useState(false)
  const [detailCode, setDetailCode] = useState('')
  const pollRef = useRef<number | null>(null)

  // 显式传入覆盖参数, 避免 setState 后闭包读到旧值
  const load = async (
    overrides: Partial<{ page: number; pageSize: number; market: string; sortBy: string; sortOrder: string }> = {},
  ) => {
    const p = overrides.page ?? page
    const ps = overrides.pageSize ?? pageSize
    const m = overrides.market ?? market
    const sb = overrides.sortBy ?? sortBy
    const so = overrides.sortOrder ?? sortOrder
    setLoading(true)
    setError('')
    try {
      const data = await api.getStocks({
        page: p,
        page_size: ps,
        search: search || undefined,
        date: date || undefined,
        market: m || undefined,
        sort_by: sb,
        sort_order: so,
      })
      setResult(data)
      setPage(p)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  // 搜索/日期变更后回到第 1 页 (state 在点按钮时已是最新值, 无闭包问题)
  const reload = () => load({ page: 1 })

  // load 的最新引用 (轮询回调里避免闭包过期)
  const loadRef = useRef(load)
  loadRef.current = load

  // ---- 数据更新 (后台任务 + 进度轮询) ----
  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const pollStatus = () => {
    api.getUpdateStatus().then((s) => {
      setUpdateStatus(s)
      if (s.status !== 'running') {
        stopPolling()
        if (s.status === 'success') loadRef.current({ page: 1 })
      }
    }).catch(() => {/* 轮询失败静默, 下次重试 */})
  }

  const startUpdate = async () => {
    try {
      const res = await api.startUpdate()
      setUpdateStatus(res.status)
      if (res.status.status === 'running') {
        stopPolling()
        pollRef.current = window.setInterval(pollStatus, 3000)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  // 挂载时自动加载列表 (Panel 常驻, 仅首次加载一次);
  // 同时检查数据更新功能是否开启 (WEB_ENABLE_UPDATE), 开启才恢复进度显示
  useEffect(() => {
    load({ page: 1 })
    api.getEnabled().then(({ update }) => {
      if (!update) return
      setUpdateEnabled(true)
      return api.getUpdateStatus().then((s) => {
        setUpdateStatus(s)
        if (s.status === 'running') {
          pollRef.current = window.setInterval(pollStatus, 3000)
        }
      })
    }).catch(() => {})
    return stopPolling
  }, [])

  // 生成分页按钮页码列表: 首页 + 末页 + 当前页附近的连续页码
  const getPageList = (): (number | string)[] => {
    if (!result) return []
    const total = result.total_pages
    if (total <= maxPageButtons + 2) {
      return Array.from({ length: total }, (_, i) => i + 1)
    }
    const cur = result.page
    const start = Math.max(2, cur - 2)
    const end = Math.min(total - 1, cur + 2)
    const list: (number | string)[] = [1]
    if (start > 2) list.push('...')
    for (let i = start; i <= end; i++) list.push(i)
    if (end < total - 1) list.push('...')
    list.push(total)
    return list
  }

  const getSortArrow = (field: string): string => {
    if (sortBy !== field) return ''
    return sortOrder === 'desc' ? ' ↓' : ' ↑'
  }

  // 点击表头排序: 同字段切换方向, 不同字段默认数值降序/代码升序
  const handleSort = (field: string) => {
    const nextSortBy = field
    const nextSortOrder = sortBy === field ? (sortOrder === 'desc' ? 'asc' : 'desc') : (field === 'code' ? 'asc' : 'desc')
    setSortBy(nextSortBy)
    setSortOrder(nextSortOrder)
    load({ page: 1, sortBy: nextSortBy, sortOrder: nextSortOrder })
  }

  // ---- 更新进度展示 ----
  const stageLabels: Record<string, string> = {
    prepare: '准备中',
    fetch: '拉取 K 线',
    etl: '计算指标',
    done: '完成',
  }

  const getUpdateProgress = (): number => {
    if (!updateStatus) return 0
    const { stage, current, total, status } = updateStatus
    if (status === 'success') return 100
    if (stage === 'prepare' || !stage) return 2
    if (stage === 'fetch') return total > 0 ? Math.max(2, Math.floor((current / total) * 80)) : 2
    if (stage === 'etl') return total > 0 ? 80 + Math.floor((current / total) * 19) : 80
    return 0
  }

  const tableHeaders: Array<{ key?: string; label: string; className?: string }> = [
    { key: 'code', label: '代码' },
    { label: '名称' },
    { label: '市场' },
    { label: '开盘', className: 'text-right' },
    { label: '最高', className: 'text-right' },
    { label: '最低', className: 'text-right' },
    { key: 'close', label: '收盘', className: 'text-right' },
    { key: 'change_percent', label: '涨跌幅', className: 'text-right' },
    { key: 'volume', label: '成交量', className: 'text-right' },
    { key: 'amount', label: '成交额', className: 'text-right' },
    { key: 'turnover_rate', label: '换手率%', className: 'text-right' },
  ]

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">股票数据</h2>
      <p className="text-gray-500 text-sm mb-4">沪深京全市场行情浏览，支持按板块筛选、搜索与排序</p>

      <IndicatorGuide
        items={[
          { term: '涨跌幅', desc: '当日累计涨跌幅度，红涨绿跌' },
          { term: '成交量/成交额', desc: '当日买卖的总手数/总金额，反映交投活跃度' },
          { term: '换手率', desc: '当日成交股数占流通股的比例，越高说明该股交易越活跃' },
          { term: '点击代码/名称', desc: '可打开该股详情，查看 K 线、技术指标与历史区间收益' },
        ]}
      />

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">搜索 (代码/名称)</label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && reload()}
            placeholder="如 600519 或 茅台"
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">市场</label>
          <select
            value={market}
            onChange={(e) => {
              const v = e.target.value
              setMarket(v)
              load({ page: 1, market: v })
            }}
            className="p-2 border border-gray-200 rounded-md"
          >
            {marketOptions.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">交易日 (留空为最新)</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">每页数量</label>
          <select
            value={pageSize}
            onChange={(e) => {
              const v = Number(e.target.value)
              setPageSize(v)
              load({ page: 1, pageSize: v })
            }}
            className="p-2 border border-gray-200 rounded-md"
          >
            {[20, 50, 100, 200].map((n) => (
              <option key={n} value={n}>{n} 条/页</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">&nbsp;</label>
          <button
            onClick={reload}
            disabled={loading}
            className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50 w-full flex-1"
          >
            {loading ? '查询中...' : '查询'}
          </button>
        </div>
      </div>

      {/* 数据更新: 触发后台增量拉取 + ETL (仅 WEB_ENABLE_UPDATE=1 时展示) */}
      {updateEnabled && (
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <button
          onClick={startUpdate}
          disabled={updateStatus?.status === 'running'}
          className="px-4 py-2 bg-emerald-600 text-white text-sm rounded-md hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {updateStatus?.status === 'running' ? '更新中...' : '拉取最新数据'}
        </button>

        {updateStatus?.status === 'running' && (
          <div className="flex-1 min-w-64">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>
                {stageLabels[updateStatus.stage] || updateStatus.stage} {updateStatus.total > 0 && `${updateStatus.current}/${updateStatus.total}`}
                <span className="ml-2 text-gray-400">({getUpdateProgress()}%)</span>
              </span>
              <span>
                {updateStatus.stage === 'etl'
                  ? `已载入 ${updateStatus.etl_loaded.toLocaleString()} 条`
                  : `新增 ${updateStatus.fetched_rows.toLocaleString()} 条`}
                {updateStatus.failed > 0 && <span className="ml-2 text-orange-500">失败 {updateStatus.failed}</span>}
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${getUpdateProgress()}%` }}
              />
            </div>
          </div>
        )}
        {updateStatus?.status === 'running' && (
          <span className="text-xs text-gray-400">后台运行中，可继续浏览其他页面</span>
        )}
        {updateStatus?.status === 'success' && (
          <span className="text-sm text-emerald-700">✅ {updateStatus.message}</span>
        )}
        {updateStatus?.status === 'error' && (
          <span className="text-sm text-red-600">❌ {updateStatus.error}</span>
        )}
      </div>
      )}

      {error && (
        <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      {result && result.success && (
        <div>
          <div className="flex items-center justify-between text-sm text-gray-500 mb-3">
            <span>
              交易日: <span className="font-medium text-gray-700">{result.date}</span>
              {result.total > 0 && ` | 共 ${result.total.toLocaleString()} 只`}
            </span>
            <span>第 {result.page} / {result.total_pages || 1} 页</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  {tableHeaders.map((h, i) => (
                    <th
                      key={i}
                      onClick={h.key ? () => handleSort(h.key!) : undefined}
                      className={`p-3 text-xs font-semibold text-gray-500 uppercase ${h.className || 'text-left'} ${h.key ? 'cursor-pointer select-none hover:text-violet-600' : ''}`}
                    >
                      {h.label}
                      {h.key && <span className="text-violet-600">{getSortArrow(h.key)}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.items.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="p-8 text-center text-gray-400">无匹配数据</td>
                  </tr>
                ) : (
                  result.items.map((s: StockRow) => (
                    <tr key={s.code} className="hover:bg-gray-50 border-b border-gray-100">
                      <td className="p-3 text-sm font-medium">
                        <button onClick={() => setDetailCode(s.code)} className="text-violet-600 hover:underline cursor-pointer">
                          {s.code}
                        </button>
                      </td>
                      <td className="p-3 text-sm">
                        <button onClick={() => setDetailCode(s.code)} className="hover:text-violet-600 hover:underline cursor-pointer">
                          {s.name}
                        </button>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-1 text-xs rounded ${getMarketColor(s.market)}`}>
                          {s.market}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-right">{s.open.toFixed(2)}</td>
                      <td className="p-3 text-sm text-right text-red-600">{s.high.toFixed(2)}</td>
                      <td className="p-3 text-sm text-right text-green-600">{s.low.toFixed(2)}</td>
                      <td className="p-3 text-sm text-right font-medium">{s.close.toFixed(2)}</td>
                      <td className={`p-3 text-sm text-right font-medium ${s.change_percent >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {s.change_percent >= 0 ? '+' : ''}{s.change_percent.toFixed(2)}%
                      </td>
                      <td className="p-3 text-sm text-right">{fmtVolume(s.volume)}</td>
                      <td className="p-3 text-sm text-right">{fmtAmount(s.amount)}</td>
                      <td className="p-3 text-sm text-right">{s.turnover_rate.toFixed(2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 分页控件 */}
          <div className="flex items-center justify-center gap-1 mt-4 flex-wrap">
            <button
              onClick={() => load({ page: Math.max(1, result.page - 1) })}
              disabled={result.page <= 1 || loading}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              上一页
            </button>
            {getPageList().map((p, i) =>
              p === '...' ? (
                <span key={`e${i}`} className="px-2 text-gray-400">…</span>
              ) : (
                <button
                  key={p}
                  onClick={() => load({ page: Number(p) })}
                  disabled={loading}
                  className={`px-3 py-1.5 text-sm rounded-md border ${
                    result.page === p
                      ? 'bg-violet-600 text-white border-violet-600'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {p}
                </button>
              )
            )}
            <button
              onClick={() => load({ page: Math.min(result.total_pages || 1, result.page + 1) })}
              disabled={result.page >= (result.total_pages || 1) || loading}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        </div>
      )}

      {detailCode && <StockDetailModal code={detailCode} onClose={() => setDetailCode('')} />}
    </div>
  )
}
