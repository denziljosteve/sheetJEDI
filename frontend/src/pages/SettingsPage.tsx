import { useEffect, useState } from 'react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Input, Label, Select } from '../components/ui/Field'
import { ApiError } from '../lib/api'
import { EXPLANATION_LANGUAGES, SKILL_LEVELS } from '../lib/constants'
import { AUTHOR } from '../lib/credits'
import {
  useAppSettings,
  useProviderModels,
  useProviders,
  useTestProvider,
  useUpdateAppSettings,
  useUpdateProvider,
} from '../lib/queries'
import { formatDate } from '../lib/utils'
import type { ProviderConfigUpdate, ProviderStatus, SkillLevel, Platform } from '../lib/types'

function errText(err: unknown): string {
  if (err instanceof ApiError) {
    const rid = err.requestId ? ` (request ${err.requestId})` : ''
    return `${err.message}${rid}`
  }
  return err instanceof Error ? err.message : 'Unexpected error'
}

function ProviderCard({ provider }: { provider: ProviderStatus }) {
  const updateMutation = useUpdateProvider()
  const testMutation = useTestProvider()
  const [apiKey, setApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [baseUrl, setBaseUrl] = useState(provider.base_url_override ?? '')
  const [model, setModel] = useState(provider.default_model ?? '')
  const [timeout, setTimeoutSec] = useState(
    provider.timeout_seconds != null ? String(provider.timeout_seconds) : '',
  )
  const [modelsWanted, setModelsWanted] = useState(false)
  const [modelsTick, setModelsTick] = useState(0)

  // Sync non-secret fields when the server state changes (after save/test).
  useEffect(() => {
    setBaseUrl(provider.base_url_override ?? '')
    setModel(provider.default_model ?? '')
    setTimeoutSec(provider.timeout_seconds != null ? String(provider.timeout_seconds) : '')
  }, [provider.base_url_override, provider.default_model, provider.timeout_seconds])

  const modelsQuery = useProviderModels(modelsWanted ? provider.name : null, modelsWanted ? modelsTick : false)
  const supportsCustomBase = provider.capabilities.custom_base_url

  const save = () => {
    const update: ProviderConfigUpdate = {}
    if (clearKey) {
      update.clear_api_key = true
    } else if (apiKey.trim()) {
      update.api_key = apiKey.trim()
    }
    if (baseUrl.trim() !== (provider.base_url_override ?? '')) {
      update.base_url = baseUrl.trim() || provider.default_base_url
    }
    if (model !== (provider.default_model ?? '')) {
      update.default_model = model // empty string clears the default model
    }
    const t = timeout.trim()
    if (t && Number(t) !== provider.timeout_seconds) {
      update.timeout_seconds = Number(t)
    }
    if (Object.keys(update).length === 0) return
    updateMutation.mutate({ provider: provider.name, update })
  }

  // Clear the sensitive field only once the server confirmed the save.
  useEffect(() => {
    if (updateMutation.isSuccess) {
      setApiKey('')
      setClearKey(false)
    }
  }, [updateMutation.isSuccess])

  const statusTone =
    provider.config_status === 'tested'
      ? 'success'
      : provider.config_status === 'configured'
        ? 'warning'
        : provider.config_status === 'failed'
          ? 'danger'
          : 'neutral'

  return (
    <Card data-testid={`provider-${provider.name}`}>
      <CardHeader
        title={provider.display_name}
        description={
          <span className="block font-mono text-xs">{provider.default_base_url}</span>
        }
        actions={<Badge tone={statusTone}>{provider.config_status}</Badge>}
      />
      <CardBody className="space-y-4 pt-2">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor={`key-${provider.name}`}>API key</Label>
            <Input
              id={`key-${provider.name}`}
              type="password"
              autoComplete="new-password"
              placeholder={
                provider.api_key_hint
                  ? `Stored: ${provider.api_key_hint} — leave blank to keep`
                  : 'Paste API key (stored encrypted)'
              }
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                if (clearKey) setClearKey(false)
              }}
              data-testid={`key-input-${provider.name}`}
            />
            <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 accent-[var(--primary)]"
                  checked={clearKey}
                  onChange={(e) => setClearKey(e.target.checked)}
                  disabled={!provider.api_key_hint}
                />
                Remove stored key
              </label>
              <span className="text-xs text-muted-foreground">
                Encrypted with Fernet · never returned to the browser · never logged
              </span>
            </div>
          </div>

          <div>
            <Label htmlFor={`base-${provider.name}`} hint={supportsCustomBase ? 'optional' : 'fixed'}>
              Base URL {supportsCustomBase ? '(self-hosted / proxy)' : ''}
            </Label>
            <Input
              id={`base-${provider.name}`}
              value={baseUrl}
              placeholder={provider.default_base_url}
              disabled={!supportsCustomBase && provider.name !== 'omniroute'}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
            {!supportsCustomBase && (
              <p className="mt-1 text-xs text-muted-foreground">
                This provider uses the official endpoint.
              </p>
            )}
          </div>

          <div>
            <Label htmlFor={`model-${provider.name}`} hint="optional">
              Default model
            </Label>
            <Input
              id={`model-${provider.name}`}
              list={`models-${provider.name}`}
              value={model}
              placeholder="Provider default"
              onChange={(e) => setModel(e.target.value)}
              data-testid={`model-input-${provider.name}`}
            />
            <datalist id={`models-${provider.name}`}>
              {(modelsQuery.data?.models ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </datalist>
            <div className="mt-1 flex items-center gap-2">
              <button
                type="button"
                className="text-xs text-primary underline-offset-2 hover:underline"
                onClick={() => {
                  if (!modelsWanted) setModelsWanted(true)
                  else setModelsTick((t) => t + 1)
                }}
              >
                {modelsQuery.isFetching
                  ? 'Loading models…'
                  : modelsQuery.data
                    ? `Refresh models (${modelsQuery.data.models.length}, ${modelsQuery.data.source})`
                    : 'List models'}
              </button>
              {modelsQuery.isError && (
                <span className="text-xs text-danger">
                  {errText(modelsQuery.error)} — type an id manually.
                </span>
              )}
            </div>
          </div>

          <div>
            <Label htmlFor={`timeout-${provider.name}`} hint="seconds, 5–600">
              Request timeout
            </Label>
            <Input
              id={`timeout-${provider.name}`}
              type="number"
              min={5}
              max={600}
              value={timeout}
              placeholder="Provider default"
              onChange={(e) => setTimeoutSec(e.target.value)}
            />
          </div>
        </div>

        {(provider.status_note || provider.verification_status) && (
          <div className="rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Adapter verification:</span>{' '}
            {provider.verification_status}
            {provider.status_note ? ` — ${provider.status_note}` : ''}
            {provider.docs_url && (
              <>
                {' · '}
                <a
                  href={provider.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  docs
                </a>
              </>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            loading={updateMutation.isPending}
            onClick={save}
            data-testid={`save-${provider.name}`}
          >
            Save
          </Button>
          <Button
            size="sm"
            variant="outline"
            loading={testMutation.isPending}
            onClick={() => testMutation.mutate(provider.name)}
            data-testid={`test-${provider.name}`}
          >
            Test connection
          </Button>
          {updateMutation.isSuccess && (
            <span role="status" className="text-xs text-success" data-testid={`saved-${provider.name}`}>
              Saved ✓
            </span>
          )}
          {updateMutation.isError && (
            <span role="alert" className="text-xs text-danger">
              {errText(updateMutation.error)}
            </span>
          )}
        </div>

        {testMutation.isSuccess && (
          <div
            role="status"
            className={`rounded-md border px-3 py-2 text-xs ${
              testMutation.data.ok
                ? 'border-success/50 bg-success/10'
                : 'border-danger/50 bg-danger/10'
            }`}
            data-testid={`test-result-${provider.name}`}
          >
            <p className="font-medium">
              {testMutation.data.ok ? 'Connection OK' : 'Connection failed'} ·{' '}
              {testMutation.data.latency_ms != null
                ? `${testMutation.data.latency_ms} ms`
                : 'no latency'}{' '}
              {testMutation.data.models_count != null &&
                `· ${testMutation.data.models_count} models`}
            </p>
            <p className="mt-0.5">{testMutation.data.message}</p>
            <p className="mt-0.5 text-muted-foreground">
              Tested {formatDate(testMutation.data.tested_at)}
            </p>
          </div>
        )}
        {testMutation.isError && (
          <div role="alert" className="rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-xs">
            Test failed: {errText(testMutation.error)}
          </div>
        )}

        {provider.last_tested_at && !testMutation.isSuccess && !testMutation.isError && (
          <p className="text-xs text-muted-foreground">
            Last test {formatDate(provider.last_tested_at)}: {provider.last_test_message}
          </p>
        )}
      </CardBody>
    </Card>
  )
}

function AppDefaultsCard() {
  const { data: settings, isPending, isError, error } = useAppSettings()
  const { data: providers } = useProviders()
  const save = useUpdateAppSettings()
  const [form, setForm] = useState({
    default_provider: '',
    default_model: '',
    fallback_provider: '',
    fallback_model: '',
    history_enabled: true,
    default_platform: 'excel' as Platform,
    default_skill_level: 'beginner' as SkillLevel,
    default_explanation_language: 'English',
  })
  const [applied, setApplied] = useState(false)

  useEffect(() => {
    if (!settings || applied) return
    setApplied(true)
    setForm({
      default_provider: settings.default_provider ?? '',
      default_model: settings.default_model ?? '',
      fallback_provider: settings.fallback_provider ?? '',
      fallback_model: settings.fallback_model ?? '',
      history_enabled: settings.history_enabled,
      default_platform: settings.default_platform,
      default_skill_level: settings.default_skill_level,
      default_explanation_language: settings.default_explanation_language,
    })
  }, [settings, applied])

  if (isPending) return <Card><CardBody>Loading settings…</CardBody></Card>
  if (isError) {
    return (
      <Card>
        <CardBody>
          <div role="alert" className="text-sm text-danger">
            Could not load settings: {errText(error)}
          </div>
        </CardBody>
      </Card>
    )
  }

  const providerOptions: { value: string; label: string; disabled?: boolean }[] = [
    { value: '', label: 'None (first configured provider wins)' },
    ...(providers ?? []).map((p) => ({
      value: p.name,
      label: `${p.display_name}${p.config_status === 'unconfigured' ? ' (not configured)' : ''}`,
      disabled: p.config_status === 'unconfigured',
    })),
  ]

  return (
    <Card data-testid="app-settings">
      <CardHeader
        title="Defaults"
        description="Used to pre-fill the workspace. Changing these never exposes secrets."
      />
      <CardBody className="space-y-4 pt-2">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="default-platform">Default platform</Label>
            <Select
              id="default-platform"
              value={form.default_platform}
              onChange={(e) => setForm({ ...form, default_platform: e.target.value as Platform })}
            >
              <option value="excel">Excel</option>
              <option value="google_sheets">Google Sheets</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="default-skill">Default explanation depth</Label>
            <Select
              id="default-skill"
              value={form.default_skill_level}
              onChange={(e) =>
                setForm({ ...form, default_skill_level: e.target.value as SkillLevel })
              }
            >
              {SKILL_LEVELS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="default-language">Default explanation language</Label>
            <Input
              id="default-language"
              maxLength={30}
              value={form.default_explanation_language}
              onChange={(e) =>
                setForm({ ...form, default_explanation_language: e.target.value })
              }
              list="language-options"
            />
            <datalist id="language-options">
              {EXPLANATION_LANGUAGES.map((l) => (
                <option key={l} value={l} />
              ))}
            </datalist>
          </div>
          <div>
            <Label htmlFor="default-provider">Default provider</Label>
            <Select
              id="default-provider"
              value={form.default_provider}
              onChange={(e) => setForm({ ...form, default_provider: e.target.value })}
            >
              {providerOptions.map((o) => (
                <option key={o.value} value={o.value} disabled={o.disabled}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="default-model" hint="optional">
              Default model
            </Label>
            <Input
              id="default-model"
              value={form.default_model}
              placeholder="Provider default"
              onChange={(e) => setForm({ ...form, default_model: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="fallback-provider">Fallback provider</Label>
            <Select
              id="fallback-provider"
              value={form.fallback_provider}
              onChange={(e) => setForm({ ...form, fallback_provider: e.target.value })}
            >
              {providerOptions.map((o) => (
                <option key={o.value} value={o.value} disabled={o.disabled}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="fallback-model" hint="optional">
              Fallback model
            </Label>
            <Input
              id="fallback-model"
              value={form.fallback_model}
              placeholder="Provider default"
              onChange={(e) => setForm({ ...form, fallback_model: e.target.value })}
            />
          </div>
        </div>

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
            checked={form.history_enabled}
            onChange={(e) => setForm({ ...form, history_enabled: e.target.checked })}
          />
          <span>
            <span className="font-medium">Save history</span> — store generated solutions in the
            local SQLite database so you can revisit them on the History page.
          </span>
        </label>

        <div className="flex items-center gap-3">
          <Button
            size="sm"
            loading={save.isPending}
            onClick={() => save.mutate(form)}
            data-testid="save-defaults"
          >
            Save defaults
          </Button>
          {save.isSuccess && (
            <span role="status" className="text-xs text-success">
              Saved ✓
            </span>
          )}
          {save.isError && (
            <span role="alert" className="text-xs text-danger">
              {errText(save.error)}
            </span>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

export function SettingsPage() {
  const { data: providers, isPending, isError, error, refetch } = useProviders()

  return (
    <div className="space-y-6" data-testid="settings-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Provider keys are encrypted at rest (Fernet) with a local master key, masked to a hint
          like ••••7890, and never sent to the browser or written to logs. Nothing here syncs
          anywhere.
        </p>
      </header>

      <AppDefaultsCard />

      <section aria-labelledby="providers-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="providers-heading" className="text-lg font-semibold">
            AI providers
          </h2>
          <p className="text-xs text-muted-foreground">
            Configure at least one provider, or paste a key for OmniRoute&apos;s base URL if you
            self-host it.
          </p>
        </div>

        {isPending && (
          <div className="grid gap-4 lg:grid-cols-2" data-testid="providers-loading">
            <Card><CardBody>Loading providers…</CardBody></Card>
            <Card><CardBody>Loading providers…</CardBody></Card>
          </div>
        )}

        {isError && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-danger/50 bg-danger/10 px-4 py-3 text-sm">
            <span>Could not load providers: {errText(error)}</span>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {(providers ?? []).map((p) => (
            <ProviderCard key={p.name} provider={p} />
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-muted p-5 text-sm text-muted-foreground">
        <h2 className="mb-2 font-semibold text-foreground">Security notes</h2>
        <ul className="list-inside list-disc space-y-1">
          <li>Keys are encrypted with Fernet (AES-128-CBC + HMAC) — the master key lives outside the database.</li>
          <li>Responses only ever include a masked hint (e.g. ••••7890); full keys are never echoed.</li>
          <li>Log redaction scrubs key-like values; request bodies are never logged raw.</li>
          <li>Generated code and formulas are never executed by sheetJEDI — you review and run them.</li>
          <li>Workbook uploads are deleted immediately after local analysis; provider context requires per-request consent.</li>
          <li>Report issues to <a className="text-primary underline-offset-2 hover:underline" href={`mailto:${AUTHOR.email}`}>{AUTHOR.email}</a>.</li>
        </ul>
      </section>
    </div>
  )
}
