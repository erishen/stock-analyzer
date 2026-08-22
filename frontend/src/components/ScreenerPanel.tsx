import { FC, useState, useEffect } from 'react'
import type { ScreenerField, ScreenerCondition, ScreenerResult } from '@/types'
import { api } from '@/services/api'
import { StockDetailModal } from './StockDetailModal'

const OPS = [
  { value: '>', label: '>' },
  { value: '>=', label: '>=' },
  { value: '<', label: '<' },
  { value: '<=', label: '<=' },
  { value: '=', label: '=' },
  { value: '!=', label: '≠' },
]

// 保存的自定义规则 (localStorage)
// key: 规则名; value: 条件 + 排序
const RULES_KEY = 'screener_rules'
const LAST_RULE_KEY = 'screener_last_rule'

interface SavedRule {
  name: string
  conditions: ScreenerCondition[]
  limit: number
  sort_field: string
  sort_dir: string
  saved_at: string
}

function loadRules(): SavedRule[] {
  try {
    const raw = localStorage.getItem(RULES_KEY)
    return raw ? (JSON.parse(raw) as SavedRule[]) : []
  } catch {
    return []
  }
}

function saveRules(rules: SavedRule[]): void {
  try {
    localStorage.setItem(RULES_KEY, JSON.stringify(rules))
  } catch {
    /* localStorage 不可用时静默失败 */
  }
}

export const ScreenerPanel: FC = () => {
  const [fields, setFields] = useState<ScreenerField[]>([])
  const [conditions, setConditions] = useState<ScreenerCondition[]>([
    { field: '', op: '>', value: 0 },
  ])
  const [limit, setLimit] = useState(50)
  const [sortField, setSortField] = useState('change_percent')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScreenerResult | null>(null)
  const [error, setError] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [assetUpdatedAt, setAssetUpdatedAt] = useState('')
  const [refreshingAsset, setRefreshingAsset] = useState(false)
  const [assetMsg, setAssetMsg] = useState('')
  const [assetRefreshEnabled, setAssetRefreshEnabled] = useState(false)
  // 规则保存: 已存规则列表 + 当前选中的规则名
  const [rules, setRules] = useState<SavedRule[]>([])
  const [selectedRule, setSelectedRule] = useState('')
  const [ruleName, setRuleName] = useState('')
  const [ruleMsg, setRuleMsg] = useState('')

  const techFields = fields.filter((f) => f.group !== '资产')
  const assetFields = fields.filter((f) => f.group === '资产')

  // 恢复某条已存规则到当前条件
  const applyRule = (r: SavedRule) => {
    setSelectedRule(r.name)
    setConditions(r.conditions.map((c) => ({ ...c })))
    setLimit(r.limit)
    setSortField(r.sort_field)
    setSortDir(r.sort_dir)
    localStorage.setItem(LAST_RULE_KEY, r.name)
  }

  // 只存条件完整的规则
  const validCond = (c: ScreenerCondition): boolean => !!c.field

  // 保存当前条件为新规则 (同名覆盖)
  const handleSaveRule = () => {
    const name = ruleName.trim()
    if (!name) {
      setRuleMsg('请输入规则名称后再保存')
      return
    }
    const conds = conditions.filter(validCond)
    if (!conds.length) {
      setRuleMsg('当前没有有效的筛选条件，无法保存')
      return
    }
    const next = [...rules.filter((r) => r.name !== name)]
    next.push({
      name,
      conditions: conds,
      limit,
      sort_field: sortField,
      sort_dir: sortDir,
      saved_at: new Date().toISOString(),
    })
    setRules(next)
    saveRules(next)
    setSelectedRule(name)
    localStorage.setItem(LAST_RULE_KEY, name)
    setRuleMsg(`已保存规则「${name}」`)
  }

  // 载入选中的已存规则
  const handleApplySelected = () => {
    const r = rules.find((x) => x.name === selectedRule)
    if (r) applyRule(r)
  }

  useEffect(() => {
    const stored = loadRules()
    setRules(stored)
    api.getScreenerFields().then((r) => {
      if (r.success && r.items.length) {
        setFields(r.items)
        // 若存在上次保存的规则: 恢复条件并默认执行查询展示
        const last = localStorage.getItem(LAST_RULE_KEY)
        const lastRule = stored.find((x) => x.name === last)
        if (lastRule) {
          applyRule(lastRule)
          runQuery(lastRule.conditions, lastRule.limit, lastRule.sort_field, lastRule.sort_dir, 1)
        }
      }
    })
    api.getAssetSnapshot().then((r) => {
      if (r.success && r.updated_at) setAssetUpdatedAt(r.updated_at)
    })
    api.getEnabled().then(({ update }) => setAssetRefreshEnabled(update)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRefreshAsset = async () => {
    setRefreshingAsset(true)
    setAssetMsg('正在拉取全市场资产快照...')
    try {
      const r = await api.refreshAssetSnapshot()
      if (r.success) {
        setAssetMsg(`已更新 ${r.count} 只股票`);
        setAssetUpdatedAt(new Date().toISOString())
      } else {
        setAssetMsg('拉取失败，东财接口可能被限流，请稍后重试')
      }
    } catch (e) {
      setAssetMsg((e as Error).message)
    } finally {
      setRefreshingAsset(false)
    }
  }

  const renderFieldOptions = (list: ScreenerField[]) =>
    list.map((f) => (
      <option key={f.field} value={f.field}>{f.label}</option>
    ))

  const renderFieldGroup = () => (
    <>
      <optgroup label="── 资产情况 ──">
        {renderFieldOptions(assetFields)}
      </optgroup>
      <optgroup label="── 技术指标 ──">
        {renderFieldOptions(techFields)}
      </optgroup>
    </>
  )

  const updateCond = (i: number, patch: Partial<ScreenerCondition>) => {
    setConditions((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)))
  }

  const addCondition = () => setConditions((cs) => [...cs, { field: '', op: '>', value: 0 }])
  const removeCondition = (i: number) =>
    setConditions((cs) => (cs.length > 1 ? cs.filter((_, idx) => idx !== i) : cs))

  const fieldLabel = (f: string) => fields.find((x) => x.field === f)?.label ?? f

  // 执行一次自定义规则查询 (参数化, 供手动触发/分页/自动恢复共用)
  const runQuery = async (
    conds: ScreenerCondition[],
    lim: number,
    sField: string,
    sDir: string,
    targetPage: number
  ) => {
    const valid = conds.filter((c) => c.field)
    if (!valid.length) return
    setLoading(true)
    setError('')
    try {
      const data = await api.runScreener({
        conditions: valid,
        limit: lim,
        offset: (targetPage - 1) * lim,
        sort_field: sField,
        sort_dir: sDir,
      })
      setResult(data)
      setPage(targetPage)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleRun = () => {
    const valid = conditions.filter((c) => c.field)
    if (!valid.length) {
      setError('请至少选择一条规则字段')
      return
    }
    runQuery(conditions, limit, sortField, sortDir, 1)
  }

  // 分页: 基于当前条件跳页
  const handlePage = (p: number) => {
    runQuery(conditions, limit, sortField, sortDir, p)
  }

  const totalPages = result?.total ? Math.max(1, Math.ceil(result.total / limit)) : 1

  const fmt = (v: unknown, digits = 2): string | number => {
    if (v === null || v === undefined || v === '') return '-'
    const n = Number(v)
    return Number.isFinite(n) ? n.toFixed(digits) : String(v)
  }

  // 展示列: 固定的 code/name/close/change_percent + 条件命中的字段
  const shownFields = conditions.filter((c) => c.field).map((c) => c.field)
  const condCols = Array.from(new Set(shownFields)).slice(0, 6)

  return (
    <div>
      <p className="text-gray-500 text-sm mb-4">
        自定义规则条件选股，全部条件需同时满足(AND)。数据为每只股票最近一个交易日。
        字段分「资产情况」(市值/股本/估值) 与「技术指标」两组，可直接混用叠加。
      </p>

      <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
        <div className="flex-1 text-sm text-gray-600">
          资产快照：
          {assetUpdatedAt
            ? <span className="text-green-600">✅ 已就绪（{assetUpdatedAt.slice(0, 16).replace('T', ' ')}）</span>
            : <span className="text-amber-600">⚠️ 未拉取，市值/估值字段将无数据</span>}
        </div>
        {assetRefreshEnabled && (
        <button
          onClick={handleRefreshAsset}
          disabled={refreshingAsset}
          className="px-4 py-1.5 text-sm bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
        >
          {refreshingAsset ? '拉取中...' : '刷新资产快照'}
        </button>
        )}
      </div>
      {assetMsg && (
        <div className={`mb-4 px-4 py-2 text-sm rounded-md ${assetMsg.includes('失败') ? 'bg-red-50 text-red-700' : 'bg-violet-50 text-violet-700'}`}>
          {assetMsg}
        </div>
      )}

      {/* 规则管理: 保存 / 载入 */}
      <div className="flex items-center gap-3 p-3 bg-violet-50/60 rounded-lg mb-4 flex-wrap">
        <span className="text-sm text-violet-700 font-medium">规则管理</span>
        <input
          type="text"
          value={ruleName}
          onChange={(e) => setRuleName(e.target.value)}
          placeholder="输入规则名称"
          className="p-2 border border-gray-200 rounded-md flex-1 min-w-[160px] text-sm"
        />
        <button
          onClick={handleSaveRule}
          className="px-4 py-2 text-sm bg-violet-600 text-white rounded-md hover:bg-violet-700"
        >
          保存当前规则
        </button>
        {rules.length > 0 && (
          <>
            <select
              value={selectedRule}
              onChange={(e) => setSelectedRule(e.target.value)}
              className="p-2 border border-gray-200 rounded-md text-sm"
            >
              <option value="">选择已保存规则...</option>
              {rules.map((r) => (
                <option key={r.name} value={r.name}>{r.name}</option>
              ))}
            </select>
            <button
              onClick={handleApplySelected}
              className="px-4 py-2 text-sm border border-violet-600 text-violet-600 rounded-md hover:bg-violet-50"
            >
              载入
            </button>
          </>
        )}
        {selectedRule && (
          <span className="text-xs text-gray-500">当前规则：{selectedRule}</span>
        )}
      </div>
      {ruleMsg && (
        <div className="mb-3 text-sm text-violet-700">{ruleMsg}</div>
      )}

      <div className="space-y-3 mb-4">
        {conditions.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <select
              value={c.field}
              onChange={(e) => updateCond(i, { field: e.target.value })}
              className="flex-1 p-2 border border-gray-200 rounded-md"
            >
              <option value="">选择指标...</option>
              {renderFieldGroup()}
            </select>
            <select
              value={c.op}
              onChange={(e) => updateCond(i, { op: e.target.value })}
              className="w-20 p-2 border border-gray-200 rounded-md text-center"
            >
              {OPS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              type="number"
              step="any"
              value={c.value}
              onChange={(e) => updateCond(i, { value: Number(e.target.value) })}
              className="w-32 p-2 border border-gray-200 rounded-md"
              placeholder="数值"
            />
            <button
              onClick={() => removeCondition(i)}
              className="px-2 py-1 text-gray-400 hover:text-red-600"
              title="删除该条件"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={addCondition}
        className="mb-4 text-sm text-violet-600 hover:underline"
      >
        + 添加条件
      </button>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">显示数量</label>
          <input
            type="number"
            value={limit}
            onChange={(e) => setLimit(Math.max(1, Number(e.target.value)))}
            className="p-2 border border-gray-200 rounded-md"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">排序字段</label>
          <select
            value={sortField}
            onChange={(e) => setSortField(e.target.value)}
            className="p-2 border border-gray-200 rounded-md"
          >
            {renderFieldGroup()}
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-gray-500 mb-1">排序方向</label>
          <select
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value)}
            className="p-2 border border-gray-200 rounded-md"
          >
            <option value="desc">从高到低</option>
            <option value="asc">从低到高</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={handleRun}
          disabled={loading}
          className="px-5 py-2 bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? '筛选中...' : '开始筛选'}
        </button>
        {result && result.success && (
          <span className="text-sm text-gray-600">
            共命中 <b className="text-violet-600">{result.total}</b> 只
            {result.date ? `（数据日期 ${result.date}）` : ''}
          </span>
        )}
      </div>

      {error && <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>}

      {result && result.success && result.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">代码</th>
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">名称</th>
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">收盘价</th>
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">涨跌幅</th>
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">换手率%</th>
                <th className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">成交额(亿)</th>
                {condCols.map((f) => (
                  <th key={f} className="p-3 text-left text-xs font-semibold text-gray-500 uppercase">
                    {fieldLabel(f)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.items.map((s, i) => (
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
                  <td className="p-3 text-sm">{fmt(s.close)}</td>
                  <td className={`p-3 text-sm ${Number(s.change_percent) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {fmt(s.change_percent)}%
                  </td>
                  <td className="p-3 text-sm">{fmt(s.turnover_rate)}%</td>
                  <td className="p-3 text-sm">
                    {fmt(Number(s.amount) ? Number(s.amount) / 1e8 : '-')}
                  </td>
                  {condCols.map((f) => (
                    <td key={f} className="p-3 text-sm">{fmt(s[f])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 分页 (仅当命中数超过单页显示时展示) */}
      {result && result.success && result.total > limit && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            onClick={() => handlePage(page - 1)}
            disabled={page <= 1 || loading}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40"
          >
            上一页
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages} 页（共 {result.total} 只）
          </span>
          <button
            onClick={() => handlePage(page + 1)}
            disabled={page >= totalPages || loading}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      )}

      {result && result.success && result.items.length === 0 && (
        <div className="p-4 bg-gray-50 text-gray-500 rounded-md">没有符合条件的股票</div>
      )}

      {selectedCode && (
        <StockDetailModal code={selectedCode} onClose={() => setSelectedCode(null)} />
      )}
    </div>
  )
}