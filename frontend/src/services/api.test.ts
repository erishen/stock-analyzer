import { describe, it, expect, afterEach, vi } from 'vitest'
import { fetchAPI } from './api'

// 保存/恢复全局 fetch
const realFetch = globalThis.fetch

function mockFetchOnce(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const spy = vi.fn(handler)
  globalThis.fetch = spy as unknown as typeof fetch
  return spy
}

afterEach(() => {
  globalThis.fetch = realFetch
})

describe('fetchAPI', () => {
  it('200 OK 返回解析后的 JSON', async () => {
    mockFetchOnce(() =>
      new Response(JSON.stringify({ success: true, base_url: 'x' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const r = await fetchAPI<{ success: boolean; base_url: string }>('/agent/settings')
    expect(r.success).toBe(true)
    expect(r.base_url).toBe('x')
  })

  it('403 + body.disabled=true 应 resolve 为 {disabled:true} 而非 reject (根治设置页误报)', async () => {
    mockFetchOnce(() =>
      new Response(
        JSON.stringify({ detail: { disabled: true, message: '模型设置仅在本地部署可用' } }),
        { status: 403, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    // 不应抛错; 应返回带 disabled 标志的对象
    const r = await fetchAPI<{ disabled?: boolean; message?: string }>('/agent/settings')
    expect(r.disabled).toBe(true)
    expect(r.message).toContain('本地')
  })

  it('403 无 disabled 标志应 reject (真正的拒绝访问)', async () => {
    mockFetchOnce(() =>
      new Response(JSON.stringify({ message: 'Forbidden' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await expect(fetchAPI('/agent/settings')).rejects.toThrow('Forbidden')
  })

  it('非 2xx 且非 403-disabled 应 reject 并带 message', async () => {
    mockFetchOnce(() =>
      new Response(JSON.stringify({ message: '服务内部错误' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await expect(fetchAPI('/x')).rejects.toThrow('服务内部错误')
  })

  it('空 body 的 2xx 应宽松 resolve 为 {success:true}', async () => {
    mockFetchOnce(() => new Response('', { status: 200 }))
    const r = await fetchAPI<{ success?: boolean }>('/ok')
    expect(r.success).toBe(true)
  })

  it('网络层错误(connect reset)应 reject 并提示服务可能冷启动', async () => {
    mockFetchOnce(() => {
      throw new Error('fetch failed')
    })
    await expect(fetchAPI('/x')).rejects.toThrow('网络请求失败')
  })
})
