import { FC } from 'react'

interface GuideItem {
  term: string
  desc: string
}

/** 可折叠的指标/术语说明 (各面板标题下展示, 展开查看通俗解释) */
export const IndicatorGuide: FC<{ title?: string; items: GuideItem[] }> = ({
  title = '指标说明',
  items,
}) => (
  <details className="mb-4 text-sm">
    <summary className="cursor-pointer text-violet-600 hover:underline select-none inline-flex items-center gap-1">
      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-violet-100 text-violet-600 text-xs font-bold">
        ?
      </span>
      {title}
    </summary>
    <div className="mt-2 p-3 bg-violet-50 rounded-lg border border-violet-100 space-y-1.5">
      {items.map((it) => (
        <div key={it.term} className="flex gap-2">
          <span className="text-violet-700 font-medium whitespace-nowrap">{it.term}</span>
          <span className="text-gray-600">：{it.desc}</span>
        </div>
      ))}
    </div>
  </details>
)