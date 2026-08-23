import { FC, useEffect, useState } from 'react'
import { api } from '@/services/api'

export const SettingsPanel: FC = () => {
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [configured, setConfigured] = useState(false)
  const [masked, setMasked] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [disabled, setDisabled] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  useEffect(() => {
    api.getLLMSettings().then((s) => {
      if (s && (s.disabled || (s.detail && s.detail.disabled))) {
        setDisabled(true)
        setLoading(false)
        return
      }
      setBaseUrl(s.base_url || '')
      setModel(s.model || '')
      setConfigured(s.configured_api_key)
      setMasked(s.api_key_masked || '')
      setLoading(false)
    }).catch((e) => {
      // fetchAPI 已把后端 403+disabled 的"功能禁用"语义 resolve 为 {disabled:true},
      // 这里只会收到真正的网络/未知错误, 才视为读取失败。
      const msg = e instanceof Error ? e.message : String(e)
      setMsg({ type: 'err', text: '读取配置失败：' + msg })
      setLoading(false)
    })
  }, [])

  const save = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const r = await api.saveLLMSettings({
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        model: model.trim(),
      })
      setMsg(r.success ? { type: 'ok', text: r.message || '已保存' } : { type: 'err', text: r.message || '保存失败' })
      setApiKey('')
      // 刷新脱敏状态
      const s = await api.getLLMSettings()
      setConfigured(s.configured_api_key)
      setMasked(s.api_key_masked || '')
    } catch {
      setMsg({ type: 'err', text: '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const r = await api.resetLLMSettings()
      setMsg(r.success ? { type: 'ok', text: r.message || '已重置' } : { type: 'err', text: r.message || '重置失败' })
      const s = await api.getLLMSettings()
      setBaseUrl(s.base_url || '')
      setModel(s.model || '')
      setConfigured(s.configured_api_key)
      setMasked(s.api_key_masked || '')
      setApiKey('')
    } catch {
      setMsg({ type: 'err', text: '重置失败' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="bg-white rounded-lg p-6 shadow-sm text-gray-500">加载配置中...</div>
  }

  if (disabled) {
    return (
      <div className="bg-white rounded-lg p-6 shadow-sm max-w-2xl">
        <h2 className="text-lg font-semibold mb-2">⚙️ 模型配置</h2>
        <p className="text-sm text-gray-500">
          模型设置仅在本地（localhost）部署可用。当前为公网/共享部署，为保证 LLM 配置（含 API Key）安全，设置功能已禁用。
          如需修改，请在本地运行后于设置中调整，或直接在服务器 <code>.env</code> 中配置 <code>LLM_API_KEY</code> / <code>LLM_BASE_URL</code> / <code>LLM_MODEL</code>。
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm max-w-2xl">
      <h2 className="text-lg font-semibold mb-1">⚙️ 模型配置</h2>
      <p className="text-sm text-gray-500 mb-4">
        配置 AI 选股使用的 LLM（OpenAI 兼容接口）。留空表示沿用 <code>.env</code> 默认配置。
        当前状态：{configured ? <>已配置 API Key（<code>{masked}</code>）</> : '未配置 API Key'}
      </p>

      <div className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-gray-700">Base URL</span>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
            className="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-gray-700">模型</span>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="gpt-4o-mini"
            className="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-gray-700">
            API Key {configured && <span className="text-xs text-gray-400">（已配置，留空则沿用）</span>}
          </span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={configured ? '••••••••••••' : 'sk-xxxx'}
            className="mt-1 w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>

        <div className="flex gap-2 pt-2">
          <button
            onClick={save}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md"
          >
            {saving ? '保存中...' : '保存配置'}
          </button>
          <button
            onClick={reset}
            disabled={saving}
            className="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-sm font-medium px-4 py-2 rounded-md"
          >
            恢复 .env 默认
          </button>
        </div>

        {msg && (
          <p className={`text-sm ${msg.type === 'ok' ? 'text-green-600' : 'text-red-600'}`}>
            {msg.text}
          </p>
        )}
      </div>
    </div>
  )
}