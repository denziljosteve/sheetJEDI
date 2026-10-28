// TanStack Query hooks wrapping the API client.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { AppSettings, GenerationRequest, ProviderConfigUpdate } from './types'

export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: api.listProviders,
    staleTime: 30_000,
  })
}

export function useProviderModels(provider: string | null, refresh: boolean | number = false) {
  return useQuery({
    queryKey: ['provider-models', provider, refresh],
    queryFn: () => api.providerModels(provider as string, refresh !== false),
    enabled: !!provider,
    retry: false,
  })
}

export function useUpdateProvider() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, update }: { provider: string; update: ProviderConfigUpdate }) =>
      api.updateProvider(provider, update),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['providers'] })
      void qc.invalidateQueries({ queryKey: ['app-settings'] })
    },
  })
}

export function useTestProvider() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: string) => api.testProvider(provider),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['providers'] })
    },
  })
}

export function useAppSettings() {
  return useQuery({
    queryKey: ['app-settings'],
    queryFn: api.getAppSettings,
  })
}

export function useUpdateAppSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (update: Partial<AppSettings>) => api.updateAppSettings(update),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['app-settings'] })
    },
  })
}

export function useGenerateSolution() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: GenerationRequest) => api.generate(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export function useHistory(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ['history', limit, offset],
    queryFn: () => api.listHistory(limit, offset),
  })
}

export function useHistoryItem(id: string | null) {
  return useQuery({
    queryKey: ['history-item', id],
    queryFn: () => api.getHistoryItem(id as string),
    enabled: !!id,
  })
}

export function useDeleteHistoryItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteHistoryItem(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['history'] })
    },
  })
}
