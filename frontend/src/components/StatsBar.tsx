import { FC } from 'react'
import type { Stats } from '@/types'

interface StatsBarProps {
  stats: Stats | null
}

const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

export const StatsBar: FC<StatsBarProps> = ({ stats }) => {
  if (!stats || !stats.success) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-lg p-5 shadow-sm animate-pulse">
            <div className="h-3 bg-gray-200 rounded w-16 mb-2"></div>
            <div className="h-7 bg-gray-200 rounded w-20"></div>
          </div>
        ))}
      </div>
    )
  }

  const items = [
    { label: '股票数量', value: formatNumber(stats.stock_count) },
    { label: '数据记录', value: formatNumber(stats.total_records) },
    { label: '日期范围', value: `${stats.min_date} ~ ${stats.max_date}`, small: true },
    { label: '技术指标', value: stats.indicator_count.toString() },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
      {items.map((item, i) => (
        <div key={i} className="bg-white rounded-lg p-5 shadow-sm">
          <h3 className="text-xs text-gray-500 uppercase mb-1">{item.label}</h3>
          <div className={`font-semibold text-gray-800 ${item.small ? 'text-base' : 'text-2xl'}`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  )
}
