import { FC, useState, useEffect } from 'react'
import { Header } from '@/components/Header'
import { StatsBar } from '@/components/StatsBar'
import { Tabs } from '@/components/Tabs'
import { ScanPanel } from '@/components/ScanPanel'
import { PaperPanel } from '@/components/PaperPanel'
import { AgentPanel } from '@/components/AgentPanel'
import { BacktestPanel } from '@/components/BacktestPanel'
import { PortfolioPanel } from '@/components/PortfolioPanel'
import { SectorPanel } from '@/components/SectorPanel'
import { MarketPanel } from '@/components/MarketPanel'
import { DictionaryPanel } from '@/components/DictionaryPanel'
import { StocksPanel } from '@/components/StocksPanel'
import { SettingsPanel } from '@/components/SettingsPanel'
import { api } from '@/services/api'
import type { Stats } from '@/types'

const App: FC = () => {
  const [activeTab, setActiveTab] = useState('agent')
  // 已访问过的 Tab 集合: 首次进入才挂载并触发加载, 之后保持挂载不丢数据。
  // 首屏只挂载 agent(AI 选股), 其余 Tab 的预热请求推迟到用户真正切入时。
  const [visited, setVisited] = useState<Set<string>>(() => new Set(['agent']))
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  const switchTab = (id: string) => {
    setActiveTab(id)
    setVisited((prev) => {
      if (prev.has(id)) return prev
      const next = new Set(prev)
      next.add(id)
      return next
    })
  }

  const loadStats = async () => {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (e) {
      console.error('Failed to load stats:', e)
    }
  }

  // 所有 Panel 常驻挂载，切 tab 仅切换显隐，避免组件卸载丢失已加载数据
  const panels = [
    { id: 'agent', node: <AgentPanel /> },
    { id: 'stocks', node: <StocksPanel /> },
    { id: 'scan', node: <ScanPanel /> },
    { id: 'paper', node: <PaperPanel /> },
    { id: 'market', node: <MarketPanel /> },
    { id: 'backtest', node: <BacktestPanel /> },
    { id: 'portfolio', node: <PortfolioPanel /> },
    { id: 'sector', node: <SectorPanel /> },
    { id: 'dict', node: <DictionaryPanel /> },
    { id: 'settings', node: <SettingsPanel /> },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-5">
        <StatsBar stats={stats} />
        <Tabs activeTab={activeTab} onTabChange={switchTab} />
        {panels.map(({ id, node }) => {
          const visible = activeTab === id
          const mounted = visible || visited.has(id)
          return (
            <div key={id} className={visible ? '' : 'hidden'}>
              {/* 未访问过的 Tab 不渲染 -> 不触发 useEffect 预热请求; 首次进入后保持挂载 */}
              {mounted ? node : null}
            </div>
          )
        })}
        <footer className="text-center py-5 text-gray-400 text-xs mt-10">
          Stock Analyzer v1.0 | Powered by React + Vite + ECharts
        </footer>
      </div>
    </div>
  )
}

export default App
