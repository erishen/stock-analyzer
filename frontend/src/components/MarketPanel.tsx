import { FC, useState } from 'react'
import { MarketPulsePanel } from './MarketPulsePanel'
import { MarketTimingPanel } from './MarketTimingPanel'

// 市场脉搏(图表) + 大盘择时(结论) 合并为一个 Tab, 子标签切换
export const MarketPanel: FC = () => {
  const [view, setView] = useState<'charts' | 'timing'>('charts')

  return (
    <div>
      <div className="flex gap-1 mb-4 bg-white p-1 rounded-lg shadow-sm w-fit">
        <button
          onClick={() => setView('charts')}
          className={`px-5 py-1.5 rounded-md text-sm transition-all ${
            view === 'charts' ? 'bg-violet-600 text-white' : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          市场脉搏
        </button>
        <button
          onClick={() => setView('timing')}
          className={`px-5 py-1.5 rounded-md text-sm transition-all ${
            view === 'timing' ? 'bg-violet-600 text-white' : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          大盘择时
        </button>
      </div>

      {view === 'charts' ? <MarketPulsePanel /> : <MarketTimingPanel />}
    </div>
  )
}