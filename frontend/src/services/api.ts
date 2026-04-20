import type { Stats, ScanResult, BacktestResult, PortfolioResult, SectorResult, MarketTimingResult } from '@/types'

const API_BASE = '/api'

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  return response.json()
}

export const api = {
  getStats: () => fetchAPI<Stats>('/stats'),

  scanSignals: (params: {
    signal_type?: string
    min_score?: number
    limit?: number
  }) => fetchAPI<ScanResult>('/scan', {
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
  }) => fetchAPI<BacktestResult>('/backtest', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  runPortfolio: (params: {
    strategies: string[]
    weight_method: string
    holding_days: number
    initial_capital: number
  }) => fetchAPI<PortfolioResult>('/portfolio', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  getSector: () => fetchAPI<SectorResult>('/sector'),

  getMarketTiming: () => fetchAPI<MarketTimingResult>('/market-timing'),
}
