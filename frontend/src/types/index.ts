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
    from_sector: string
    to_sector: string
    signal_type: string
    confidence: number
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
