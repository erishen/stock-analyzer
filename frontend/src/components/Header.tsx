import { FC } from 'react'

export const Header: FC = () => {
  return (
    <header className="bg-gradient-to-r from-violet-600 to-purple-600 text-white py-5 mb-5">
      <div className="max-w-7xl mx-auto px-5">
        <h1 className="text-2xl font-semibold">📈 Stock Analyzer</h1>
        <p className="opacity-90 text-sm">股票分析器 - 信号扫描、策略回测、组合分析</p>
      </div>
    </header>
  )
}
