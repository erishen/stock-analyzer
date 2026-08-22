export interface Stats {
  success: boolean
  stock_count: number
  total_records: number
  min_date: string
  max_date: string
  indicator_count: number
  error: string
}

export interface Signal {
  code: string
  name: string
  signal_type: string
  strength: string
  score: number
  price: number
  change_percent: number
  date: string
}

export interface ScanResult {
  success: boolean
  total_stocks: number
  signals_found: number
  signals: Signal[]
  summary: Record<string, number>
  error: string
}

export interface ScreenerField {
  field: string
  label: string
  group?: string
}

export interface ScreenerFieldsResult {
  success: boolean
  items: ScreenerField[]
  error: string
}

export interface AssetSnapshotResult {
  success: boolean
  updated_at: string
  items: Array<Record<string, unknown> & { code: string; name: string }>
}

export interface AssetRefreshResult {
  success: boolean
  count: number
  source?: string
  updated_at?: string
  error?: string
}

export interface ScreenerCondition {
  field: string
  op: string
  value: number
}

export interface ScreenerResult {
  success: boolean
  total: number
  date: string
  items: Array<Record<string, unknown> & { code: string; name: string }>
  error: string
}

export interface Trade {
  code: string
  name: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  profit_percent: number
}

export interface EquityPoint {
  date: string
  equity: number
}

export interface BacktestResult {
  success: boolean
  strategy_name: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  volatility: number
  total_trades: number
  win_rate: number
  profit_factor: number
  trades: Trade[]
  equity_curve: EquityPoint[]
  error: string
}

export interface StrategyResult {
  name: string
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
}

export interface OptimizeResult {
  success: boolean
  strategy: string
  best_params: Record<string, number | string>
  best_return: number
  best_sharpe: number
  best_drawdown: number
  total_combinations: number
  train_start: string
  train_end: string
  val_start: string
  val_end: string
  val_return: number
  val_sharpe: number
  val_drawdown: number
  top_results: Array<{
    params: Record<string, number | string>
    total_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
  }>
  error: string
}

export interface OptimizeTask {
  success: boolean
  task_id: string
  status: string
  progress: number
  total: number
  stage: string
  result: OptimizeResult | null
  error: string
}

export interface PortfolioResult {
  success: boolean
  name: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  volatility: number
  diversification_ratio: number
  strategy_weights: Record<string, number>
  correlation_matrix: Record<string, Record<string, number>>
  strategy_results: StrategyResult[]
  error: string
}

export interface SectorItem {
  name: string
  momentum: number
  strength: string
  stock_count: number
  top_stocks: string[]
}

export interface SectorResult {
  success: boolean
  analysis_date: string
  sectors: SectorItem[]
  rotation_signals: Array<{
    sector: string
    signal: string
    score: number
    confidence: number
    reason: string
  }>
  error: string
}

export interface MarketTimingResult {
  success: boolean
  state: string
  score: number
  position_advice: string
  indicators: Record<string, {
    value: number
    signal: string
  }>
  error: string
}

export interface StockRow {
  code: string
  name: string
  market: string
  open: number
  high: number
  low: number
  close: number
  change_percent: number
  volume: number
  amount: number
  turnover_rate: number
}

export interface StocksPageResult {
  success: boolean
  date: string
  total: number
  page: number
  page_size: number
  total_pages: number
  items: StockRow[]
  error: string
}

export interface KlinePoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  change_percent: number
  ma5: number
  ma10: number
  ma20: number
  ma60: number
}

export interface StockDetail {
  success: boolean
  code: string
  name: string
  market: string
  latest: {
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    turnover_rate: number
    change_percent: number
  }
  indicators: {
    ma5: number
    ma10: number
    ma20: number
    ma60: number
    macd: number
    macd_hist: number
    rsi: number
    kdj_k: number
    kdj_d: number
    kdj_j: number
    boll_upper: number
    boll_mid: number
    boll_lower: number
    atr: number
  }
  period_returns: Record<string, number | null>
  kline: KlinePoint[]
  asset: {
    code: string
    name: string
    close: number | null
    change_percent: number | null
    volume: number | null
    amount: number | null
    volume_ratio: number | null
    turnover_rate: number | null
    total_market_value: number | null
    float_market_value: number | null
    total_shares: number | null
    float_shares: number | null
    pe: number | null
    pb: number | null
  }
  error: string
}

export interface UpdateStatus {
  status: 'idle' | 'running' | 'success' | 'error'
  stage: 'prepare' | 'fetch' | 'etl' | 'done' | ''
  total: number
  current: number
  fetched_rows: number
  failed: number
  etl_loaded: number
  message: string
  started_at: string
  finished_at: string
  error: string
}

export interface UpdateStartResult {
  success: boolean
  message: string
  status: UpdateStatus
}

export interface PaperPosition {
  code: string
  name: string
  buy_date: string
  buy_price: number
  shares: number
  cost: number
  current_price: number | null
  change_percent: number
  value: number
  pnl: number
  pnl_pct: number
  weight: number
  stop_loss: number
  take_profit: number
  action: string
  level: 'danger' | 'success' | 'warning' | 'info' | 'muted'
  advice: string
  reasons: string[]
}

export interface PaperClosedRecord {
  code: string
  name: string
  sell_date: string
  buy_date: string
  buy_price: number
  sell_price: number
  shares: number
  profit: number
  profit_pct: number
}

export interface PaperResult {
  success: boolean
  updated_at: string
  market: { state: string; advice: string }
  summary: {
    position_count: number
    total_cost: number
    total_value: number
    total_pnl: number
    total_pnl_pct: number
    max_weight: number
    danger_count: number
  }
  positions: PaperPosition[]
  closed: PaperClosedRecord[]
}

export interface MarketHistory {
  success: boolean
  days: number
  start_date: string
  end_date: string
  dates: string[]
  avg_close: (number | null)[]
  avg_ma5: (number | null)[]
  avg_ma20: (number | null)[]
  avg_change: (number | null)[]
  avg_rsi: (number | null)[]
  breadth: (number | null)[]
  volatility: (number | null)[]
  error: string
}

export interface AgentChart {
  type: 'bar' | 'line' | 'pie' | 'none'
  title?: string
  x?: string
  y?: string[]
  dataset?: Record<string, unknown>[]
}

export interface AgentEvent {
  name: 'text2sql' | 'sql_fix'
  attempt: number
  sql?: string
  reasoning?: string
  row_count?: number
  error?: string
}

export interface AgentChatResult {
  success: boolean
  message?: string
  sql?: string
  reasoning?: string
  columns?: string[]
  rows?: Record<string, unknown>[]
  row_count?: number
  truncated?: boolean
  answer?: string
  chart?: AgentChart | null
  followups?: string[]
  events?: AgentEvent[]
}

export interface LLMSettings {
  success: boolean
  message?: string
  base_url: string
  model: string
  configured_api_key: boolean
  api_key_masked: string
  disabled?: boolean
  detail?: { disabled?: boolean; message?: string }
}
