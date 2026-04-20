import { FC } from 'react'

interface TabsProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

const tabs = [
  { id: 'scan', label: '🔍 信号扫描' },
  { id: 'backtest', label: '📊 策略回测' },
  { id: 'portfolio', label: '📦 组合分析' },
  { id: 'sector', label: '🏭 行业轮动' },
  { id: 'timing', label: '⏰ 大盘择时' },
]

export const Tabs: FC<TabsProps> = ({ activeTab, onTabChange }) => {
  return (
    <div className="flex gap-1 mb-5 bg-white p-1 rounded-lg shadow-sm flex-wrap">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`px-5 py-2 border-none rounded-md text-sm cursor-pointer transition-all
            ${activeTab === tab.id
              ? 'bg-violet-600 text-white'
              : 'bg-transparent text-gray-600 hover:bg-gray-100'
            }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
