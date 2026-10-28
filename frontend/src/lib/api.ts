// Fetch-based API client for the sheetJEDI backend.
// Never handles provider secrets beyond sending them to the backend once;
// the backend stores them encrypted and returns only masked hints.

import type {
  ApiErrorBody,
  AppSettings,
  GenerationRequest,
  GenerationResponse,
  HistoryPage,
  ModelListResponse,
  ProviderConfigUpdate,
  ProviderStatus,
  ProviderTestResult,
  SolutionDetail,
  SolutionResponse,
  WorkbookAnalysis,
} from './types'

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown
  requestId?: string

  constructor(
    code: string,
    message: string,
    status: number,
    details?: unknown,
    requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
    this.requestId = requestId
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let code = 'http_error'
  let message = `Request failed (HTTP ${response.status})`
  let details: unknown
  let requestId: string | undefined
  try {
    const body = (await response.json()) as ApiErrorBody
    if (body?.error) {
      code = body.error.code || code
      message = body.error.message || message
      details = body.error.details
      requestId = body.error.request_id
    }
  } catch {
    // Non-JSON error body; keep the generic message.
  }
  return new ApiError(code, message, response.status, details, requestId)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers:
      init?.body instanceof FormData
        ? (init?.headers as Record<string, string> | undefined)
        : { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string>) },
    ...init,
  })
  if (!response.ok) {
    throw await parseError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),

  // Providers & settings
  listProviders: () => request<ProviderStatus[]>('/providers'),
  updateProvider: (provider: string, update: ProviderConfigUpdate) =>
    request<ProviderStatus>(`/settings/providers/${provider}`, {
      method: 'PUT',
      body: JSON.stringify(update),
    }),
  testProvider: (provider: string) =>
    request<ProviderTestResult>(`/providers/${provider}/test`, { method: 'POST' }),
  providerModels: (provider: string, refresh = false) =>
    request<ModelListResponse>(
      `/providers/${provider}/models${refresh ? '?refresh=true' : ''}`,
    ),
  getAppSettings: () => request<AppSettings>('/settings/app'),
  updateAppSettings: (update: Partial<AppSettings>) =>
    request<AppSettings>('/settings/app', { method: 'PUT', body: JSON.stringify(update) }),

  // Generation
  generate: (body: GenerationRequest) =>
    request<GenerationResponse>('/solutions/generate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  validateSolution: (payload: unknown) =>
    request<{ valid: boolean; errors: string[] }>('/solutions/validate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Files
  analyzeFile: async (file: File, consent: boolean): Promise<WorkbookAnalysis> => {
    const form = new FormData()
    form.append('file', file)
    form.append('consent', consent ? 'true' : 'false')
    return request<WorkbookAnalysis>('/files/analyze', { method: 'POST', body: form })
  },
  deleteFile: (fileId: string) =>
    request<void>(`/files/${fileId}`, { method: 'DELETE' }),

  // History
  listHistory: (limit = 20, offset = 0) =>
    request<HistoryPage>(`/history?limit=${limit}&offset=${offset}`),
  getHistoryItem: (id: string) => request<SolutionDetail>(`/history/${id}`),
  deleteHistoryItem: (id: string) =>
    request<void>(`/history/${id}`, { method: 'DELETE' }),
}

export type { SolutionResponse }
