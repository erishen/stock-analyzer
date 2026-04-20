import { FC, useState, useEffect } from 'react'
import { Header } from '@/components/Header'
import { StatsBar } from '@/components/StatsBar'
import { Tabs } from '@/components/Tabs'
import { ScanPanel } from '@/components/ScanPanel'
import { BacktestPanel } from '@/components/BacktestPanel'
import { PortfolioPanel } from '@/components/PortfolioPanel'
import { SectorPanel } from '@/components/SectorPanel'
import { MarketTimingPanel } from '@/components/MarketTimingPanel'
import { api } from '@/services/api'
import type { Stats } from '@/types'

const App: FC = () => {
  const [activeTab, setActiveTab] = useState('scan')
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (e) {
      console.error('Failed to load stats:', e)
    }
  }

  const renderPanel = () => {
    switch (activeTab) {
      case 'scan':
        return <ScanPanel />
      case 'backtest':
        return <BacktestPanel />
      case 'portfolio':
        return <PortfolioPanel />
      case 'sector':
        return <SectorPanel />
      case 'timing':
        return <MarketTimingPanel />
      default:
        return <ScanPanel />
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-5">
        <StatsBar stats={stats} />
        <Tabs activeTab={activeTab} onTabChange={setActiveTab} />
        {renderPanel()}
        <footer className="text-center py-5 text-gray-400 text-xs mt-10">
          Stock Analyzer v1.0 | Powered by React + Vite + ECharts
        </footer>
      </div>
    </div>
  )
}

export default App
