import { FC, useEffect, useState } from 'react'
import type { MethodologyResult } from '@/types'
import { api } from '@/services/api'

export const MethodologyPanel: FC = () => {
  const [data, setData] = useState<MethodologyResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .getMethodology()
      .then((d) => (d.success ? setData(d) : setError('方法论内容不可用')))
      .catch((e) => setError((e as Error).message))
  }, [])

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-5 text-sm text-red-600">
        加载方法论失败：{error}
      </div>
    )
  }

  if (!data) {
    return <div className="bg-white rounded-lg shadow-sm p-5 text-sm text-gray-500">加载中…</div>
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow-sm p-5">
        <h2 className="text-lg font-semibold text-gray-800">📖 方法论 / 算法说明</h2>
        <p className="text-sm text-gray-600 mt-2">
          这里写的是代码里真实发生的口径：每个算法做什么、怎么算、哪些地方是近似、哪些偏差没有消除。
          数据口径以本机分析库为准，不承诺收益。
        </p>
        <div className="flex flex-wrap gap-2 mt-3">
          {data.sections.map((s) => (
            <button
              key={s.id}
              onClick={() => document.getElementById(`method-${s.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              className="px-3 py-1 text-xs rounded-md bg-violet-50 text-violet-700 border border-violet-200 cursor-pointer hover:bg-violet-100"
            >
              {s.title}
            </button>
          ))}
          <span className="px-3 py-1 text-xs text-gray-400 self-center">更新于 {data.updated_at}</span>
        </div>
      </div>

      {data.sections.map((section) => (
        <div key={section.id} id={`method-${section.id}`} className="bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-base font-semibold text-gray-800">{section.title}</h3>
          <p className="text-sm text-gray-600 mt-1">{section.summary}</p>

          <div className="mt-4 space-y-3">
            {section.items.map((item) => (
              <div key={item.name} className="border border-gray-100 rounded-md p-4 bg-gray-50/60">
                <div className="text-sm font-semibold text-gray-800">{item.name}</div>
                <dl className="mt-2 space-y-1.5 text-sm">
                  <div className="flex gap-2">
                    <dt className="shrink-0 text-gray-400 w-14">做什么</dt>
                    <dd className="text-gray-700">{item.what}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="shrink-0 text-gray-400 w-14">怎么算</dt>
                    <dd className="text-gray-700">{item.how}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="shrink-0 text-amber-600 w-14">局限</dt>
                    <dd className="text-amber-800">{item.limits}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-5 text-sm text-amber-800">
        {data.disclaimer}
      </div>
    </div>
  )
}
