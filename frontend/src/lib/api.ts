/** Everything HTTP. Same-origin via the Vite proxy, so the session cookie
 *  rides along automatically and there is no token to plumb. */
import type { Dataset, SolveResult } from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail[0]?.msg ?? detail
    } catch {
      /* non-JSON error body — statusText will do */
    }
    throw new ApiError(res.status, detail)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export interface User {
  id: number
  email: string
}
export interface DatasetSummary {
  id: number
  name: string
  updated_at: string
  has_solution: boolean
  counts: { classes: number; teachers: number; subjects: number; rooms: number }
}
export interface SampleInfo {
  key: string
  label: string
  days: number
  periods_per_day: number
  classes: number
  teachers: number
  subjects: number
  rooms: number
}
export interface DatasetDetail {
  id: number
  name: string
  data: Record<string, unknown>
  last_solution: SolveResult | null
  updated_at: string
}
export interface ParsedSheet {
  name: string
  headers: string[]
  rows: (string | number | null)[][]
}

export const api = {
  signup: (email: string, password: string) =>
    request<{ user: User }>('POST', '/api/auth/signup', { email, password }),
  login: (email: string, password: string) =>
    request<{ user: User }>('POST', '/api/auth/login', { email, password }),
  logout: () => request<void>('POST', '/api/auth/logout'),
  me: () => request<{ user: User }>('GET', '/api/auth/me'),

  samples: () => request<SampleInfo[]>('GET', '/api/samples'),

  listDatasets: () => request<DatasetSummary[]>('GET', '/api/datasets'),
  createDataset: (body: { name?: string; sample?: string; data?: unknown }) =>
    request<DatasetDetail>('POST', '/api/datasets', body),
  getDataset: (id: number) => request<DatasetDetail>('GET', `/api/datasets/${id}`),
  saveDataset: (id: number, body: { name?: string; data?: Dataset }) =>
    request<void>('PUT', `/api/datasets/${id}`, body),
  deleteDataset: (id: number) => request<void>('DELETE', `/api/datasets/${id}`),
  solve: (id: number, time_limit: number, seed: number) =>
    request<SolveResult>('POST', `/api/datasets/${id}/solve`, { time_limit, seed }),

  parseSheet: async (file: File): Promise<{ sheets: ParsedSheet[] }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/import/parse', { method: 'POST', body: form })
    if (!res.ok) {
      const j = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, j.detail ?? res.statusText)
    }
    return res.json()
  },
}
