import type { Stats, ScanResult, ScreenerFieldsResult, AssetSnapshotResult, AssetRefreshResult, ScreenerResult, ScreenerCondition, BacktestResult, OptimizeTask, PortfolioResult, SectorResult, MarketTimingResult, MarketHistory, StocksPageResult, StockDetail, UpdateStatus, UpdateStartResult, PaperResult, AgentChatResult, LLMSettings } from '@/types'

const API_BASE = '/api'

// Agent 对话令牌: 私有部署在后端设 WEB_CHAT_TOKEN 后, 前端需带 Bearer;
// 公开 Demo(AGENT_CHAT_PUBLIC=1) 不填也能用。存 localStorage, 不随请求外泄到服务端以外的任何地方。
const WEB_CHAT_TOKEN_KEY = 'stock-analyzer:web_chat_token'

export function getWebChatToken(): string {
  try {
    return localStorage.getItem(WEB_CHAT_TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setWebChatToken(token: string): void {
  try {
    if (token) localStorage.setItem(WEB_CHAT_TOKEN_KEY, token)
    else localStorage.removeItem(WEB_CHAT_TOKEN_KEY)
  } catch {
    /* 忽略隐私模式等存储异常 */
  }
}

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (endpoint === '/agent/chat') {
    const tk = getWebChatToken().trim()
    if (tk) headers['Authorization'] = `Bearer ${tk}`
  }
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })
  return response.json()
}

export const api = {
  getStats: () => fetchAPI<Stats>('/stats'),

  scanSignals: (params: {
    signal_type?: string
    min_score?: number
    limit?: number
    refresh?: boolean
  }) => fetchAPI<ScanResult>('/scan', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  getScreenerFields: () => fetchAPI<ScreenerFieldsResult>('/screener/fields'),

  getAssetSnapshot: () => fetchAPI<AssetSnapshotResult>('/asset/snapshot'),

  refreshAssetSnapshot: () => fetchAPI<AssetRefreshResult>('/asset/refresh', { method: 'POST' }),

  runScreener: (params: {
    conditions: ScreenerCondition[]
    limit?: number
    offset?: number
    sort_field?: string
    sort_dir?: string
  }) => fetchAPI<ScreenerResult>('/screener', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  runBacktest: (params: {
    strategy: string
    holding_days: number
    initial_capital: number
    min_price: number
    stop_loss: number
    take_profit: number
    start_date?: string
    end_date?: string
    refresh?: boolean
  }) => fetchAPI<BacktestResult>('/backtest', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  runOptimize: (params: {
    strategy: string
    start_date?: string
    end_date?: string
    initial_capital?: number
  }) => fetchAPI<OptimizeTask>('/optimize', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  optimizeStatus: (taskId: string) => fetchAPI<OptimizeTask>(`/optimize/status/${taskId}`),

  runPortfolio: (params: {
    strategies: string[]
    weight_method: string
    holding_days: number
    initial_capital: number
    refresh?: boolean
  }) => fetchAPI<PortfolioResult>('/portfolio', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  getSector: (refresh?: boolean) => {
    const qs = refresh ? '?refresh=true' : ''
    return fetchAPI<SectorResult>(`/sector${qs}`)
  },

  getMarketTiming: (refresh?: boolean) => {
    const qs = refresh ? '?refresh=true' : ''
    return fetchAPI<MarketTimingResult>(`/market-timing${qs}`)
  },

  getMarketHistory: (days = 90) => fetchAPI<MarketHistory>(`/market/history?days=${days}`),

  getStocks: (params: {
    page?: number
    page_size?: number
    search?: string
    date?: string
    market?: string
    sort_by?: string
    sort_order?: string
  }) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.set(k, String(v))
    })
    return fetchAPI<StocksPageResult>(`/stocks?${qs.toString()}`)
  },

  getStockDetail: (code: string, limit = 120, days = 2500) =>
    fetchAPI<StockDetail>(`/stock/${code}?limit=${limit}&days=${days}`),

  getPaper: () => fetchAPI<PaperResult>('/paper'),

  addPaperPosition: (params: {
    code: string
    buy_price: number
    shares: number
    buy_date?: string
    stop_loss?: number
    take_profit?: number
  }) => fetchAPI<{ success: boolean; message: string }>('/paper/position', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  closePaperPosition: (params: {
    code: string
    sell_price: number
    sell_date?: string
    shares?: number
  }) => fetchAPI<{ success: boolean; message: string }>('/paper/close', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  startUpdate: () => fetchAPI<UpdateStartResult>('/update', { method: 'POST' }),

  getUpdateStatus: () => fetchAPI<UpdateStatus>('/update/status'),

  getEnabled: () => fetchAPI<{ update: boolean }>('/enabled'),

  agentChat: (messages: { role: string; content: string }[]) =>
    fetchAPI<AgentChatResult>('/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ messages }),
    }),

  getLLMSettings: () => fetchAPI<LLMSettings>('/agent/settings'),

  saveLLMSettings: (params: { base_url?: string; api_key?: string; model?: string }) =>
    fetchAPI<LLMSettings>('/agent/settings', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  resetLLMSettings: () => fetchAPI<LLMSettings>('/agent/settings/reset', { method: 'POST' }),
}
