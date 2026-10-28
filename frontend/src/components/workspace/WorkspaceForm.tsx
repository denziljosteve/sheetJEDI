import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { clearAttachment, readAttachment, type Attachment } from '../../lib/attachment'
import {
  EXAMPLES,
  EXPLANATION_LANGUAGES,
  PRESETS,
  SKILL_LEVELS,
  TASK_TYPE_LABELS,
  guidedFieldsFor,
  type Preset,
} from '../../lib/constants'
import type { GenerationRequest, TaskType } from '../../lib/types'
import { cn } from '../../lib/utils'
import { useAppSettings, useProviderModels, useProviders } from '../../lib/queries'
import { Button } from '../ui/Button'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { Input, Label, Select, Textarea } from '../ui/Field'

const TASK_TYPES = [
  'formula',
  'vba_macro',
  'office_script',
  'apps_script',
  'data_cleaning',
  'data_analysis',
  'reporting',
  'charts',
  'troubleshooting',
  'other',
] as const

const formSchema = z.object({
  request: z
    .string()
    .trim()
    .min(3, 'Describe what you need (at least 3 characters).')
    .max(6000, 'Keep the request under 6000 characters.'),
  platform: z.enum(['excel', 'google_sheets']),
  taskType: z.enum(TASK_TYPES),
  skillLevel: z.enum(['beginner', 'intermediate', 'advanced']),
  explanationLanguage: z.string().trim().min(1, 'Choose an explanation language.').max(30),
  excelVersion: z.string().max(60),
  sheetsVersion: z.string().max(60),
  provider: z.string().max(50),
  model: z.string().max(256),
  useFallback: z.boolean(),
  includeFileContext: z.boolean(),
  context: z.object({
    worksheet_names: z.string().max(2000),
    column_names: z.string().max(4000),
    input_data_description: z.string().max(4000),
    expected_result: z.string().max(4000),
    constraints: z.string().max(4000),
    existing_formula_or_code: z.string().max(8000),
    error_message: z.string().max(2000),
    sample_data: z.string().max(8000),
    extra_notes: z.string().max(4000),
  }),
})

type FormValues = z.infer<typeof formSchema>

const CONTEXT_FIELDS: { name: keyof FormValues['context']; label: string; hint?: string; multiline?: boolean }[] = [
  { name: 'worksheet_names', label: 'Worksheet names', hint: 'e.g. Orders, Products, Summary' },
  { name: 'column_names', label: 'Columns / layout', hint: 'e.g. A: OrderID, B: Date, C: Amount' },
  { name: 'input_data_description', label: 'Input data', hint: 'Describe what the data contains' },
  { name: 'expected_result', label: 'Expected result', hint: 'What success looks like' },
  { name: 'constraints', label: 'Constraints', hint: 'e.g. no macros allowed, must work in Excel 2016' },
  { name: 'existing_formula_or_code', label: 'Existing formula / code', hint: 'What you have now', multiline: true },
  { name: 'error_message', label: 'Error message', hint: 'Exact text if something fails' },
  { name: 'sample_data', label: 'Sample data (CSV)', hint: 'Small excerpt grounds the answer', multiline: true },
  { name: 'extra_notes', label: 'Extra notes', multiline: true },
]

interface WorkspaceFormProps {
  preset: Preset | null
  loading: boolean
  error: string | null
  onSubmitRequest: (body: GenerationRequest) => void
}

export function WorkspaceForm({ preset, loading, error, onSubmitRequest }: WorkspaceFormProps) {
  const { data: settings } = useAppSettings()
  const { data: providers } = useProviders()
  const [attachment, setAttachment] = useState<Attachment | null>(() => readAttachment())
  const [defaultsApplied, setDefaultsApplied] = useState(false)

  const defaultValues: FormValues = {
    request: '',
    platform: preset?.platform ?? 'excel',
    taskType: preset?.taskType ?? 'formula',
    skillLevel: 'beginner',
    explanationLanguage: 'English',
    excelVersion: '',
    sheetsVersion: '',
    provider: '',
    model: '',
    useFallback: true,
    includeFileContext: false,
    context: {
      worksheet_names: '',
      column_names: '',
      input_data_description: '',
      expected_result: '',
      constraints: '',
      existing_formula_or_code: '',
      error_message: '',
      sample_data: '',
      extra_notes: '',
    },
  }

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const platform = watch('platform')
  const taskType = watch('taskType')
  const provider = watch('provider')
  const requestText = watch('request')

  // Apply settings-based defaults once settings load (form still pristine).
  useEffect(() => {
    if (!settings || defaultsApplied) return
    setDefaultsApplied(true)
    reset((current) => ({
      ...current,
      skillLevel: settings.default_skill_level,
      explanationLanguage: settings.default_explanation_language,
      platform: preset?.platform ?? settings.default_platform,
      taskType: preset?.taskType ?? current.taskType,
      provider: settings.default_provider ?? '',
    }))
  }, [settings, defaultsApplied, reset, preset])

  const guidedDefs = guidedFieldsFor(taskType)
  const [guidedValues, setGuidedValues] = useState<Record<string, string>>({})

  const examples = useMemo(() => {
    const presetSlug = PRESETS.find((p) => p.taskType === taskType)?.slug
    return (presetSlug && EXAMPLES[presetSlug]) || []
  }, [taskType])

  const modelsQuery = useProviderModels(provider || null)

  const configuredProviders = useMemo(() => {
    return (providers ?? []).map((p) => ({
      value: p.name,
      label: `${p.display_name}${p.config_status === 'unconfigured' ? ' (not configured)' : ''}`,
      configured: p.config_status !== 'unconfigured',
    }))
  }, [providers])

  const applyExample = (example: (typeof EXAMPLES)[string][number]) => {
    reset(
      (current) => ({
        ...current,
        request: example.prompt,
        platform: example.platform,
        taskType: example.taskType,
        context: { ...current.context, error_message: '' },
      }),
      { keepErrors: false },
    )
    setGuidedValues(example.guided ?? {})
  }

  const onTaskTypeChange = (next: TaskType) => {
    // Guided keys are task-specific; clear stale values when switching.
    setGuidedValues({})
    reset((current) => ({ ...current, taskType: next }))
  }

  const submit = handleSubmit((values) => {
    const context: GenerationRequest['context'] = {}
    for (const field of CONTEXT_FIELDS) {
      const v = values.context[field.name]
      if (v && v.trim()) context[field.name] = v.trim()
    }

    const guided: Record<string, string> = {}
    for (const def of guidedDefs) {
      const v = (guidedValues[def.key] ?? '').trim()
      if (v) guided[def.key] = v.slice(0, 2000)
    }

    const body: GenerationRequest = {
      request: values.request.trim(),
      platform: values.platform,
      task_type: values.taskType,
      task_category: preset?.slug ?? null,
      excel_version: values.platform === 'excel' && values.excelVersion ? values.excelVersion : null,
      sheets_version:
        values.platform === 'google_sheets' && values.sheetsVersion ? values.sheetsVersion : null,
      skill_level: values.skillLevel,
      explanation_language: values.explanationLanguage,
      context,
      guided,
      provider: values.provider || null,
      model: values.model || null,
      use_fallback: values.useFallback,
      file_id: attachment && values.includeFileContext ? attachment.file_id : null,
      include_file_context: !!(attachment && values.includeFileContext),
    }
    onSubmitRequest(body)
  })

  const fieldError = (message?: string) =>
    message ? (
      <p role="alert" className="mt-1 text-xs text-danger">
        {message}
      </p>
    ) : null

  return (
    <form onSubmit={submit} noValidate data-testid="workspace-form" className="space-y-5">
      <Card>
        <CardHeader
          title="What do you need?"
          description="Describe the task in plain language — the more context, the sharper the solution."
        />
        <CardBody className="space-y-4">
          {examples.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Try an example
              </p>
              <div className="flex flex-wrap gap-2">
                {examples.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => applyExample(ex)}
                    className="rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-primary"
                    data-testid="example-chip"
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label htmlFor="request" required>
              Your request
            </Label>
            <Textarea
              id="request"
              rows={5}
              placeholder={
                preset
                  ? `e.g. ${preset.description}`
                  : 'e.g. Look up the price from the Products sheet by matching the SKU in column A…'
              }
              aria-invalid={errors.request ? true : undefined}
              aria-describedby={errors.request ? 'request-error' : 'request-count'}
              {...register('request')}
            />
            <div className="mt-1 flex items-center justify-between">
              <span id="request-error">{fieldError(errors.request?.message)}</span>
              <span id="request-count" className="text-xs text-muted-foreground">
                {requestText?.length ?? 0}/6000
              </span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="platform">Platform</Label>
              <Select id="platform" {...register('platform')}>
                <option value="excel">Excel (desktop / web / Mac)</option>
                <option value="google_sheets">Google Sheets</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="taskType">Task type</Label>
              <Select
                id="taskType"
                onChange={(e) => onTaskTypeChange(e.target.value as TaskType)}
                value={taskType}
              >
                {TASK_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {TASK_TYPE_LABELS[t]}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="skillLevel">Explanation depth</Label>
              <Select id="skillLevel" {...register('skillLevel')}>
                {SKILL_LEVELS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="explanationLanguage">Explanation language</Label>
              <Select id="explanationLanguage" {...register('explanationLanguage')}>
                {EXPLANATION_LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </Select>
              {fieldError(errors.explanationLanguage?.message)}
            </div>
            {platform === 'excel' && (
              <div className="sm:col-span-2">
                <Label htmlFor="excelVersion" hint="optional">
                  Excel version
                </Label>
                <Input
                  id="excelVersion"
                  placeholder="e.g. Microsoft 365, Excel 2021, Excel for Mac"
                  {...register('excelVersion')}
                />
                {fieldError(errors.excelVersion?.message)}
              </div>
            )}
            {platform === 'google_sheets' && (
              <div className="sm:col-span-2">
                <Label htmlFor="sheetsVersion" hint="optional">
                  Google Sheets context
                </Label>
                <Input
                  id="sheetsVersion"
                  placeholder="e.g. personal Workspace, workspace with restricted add-ons"
                  {...register('sheetsVersion')}
                />
                {fieldError(errors.sheetsVersion?.message)}
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Guided details"
          description="Optional structured answers — they make formula and code generation markedly better."
        />
        <CardBody>
          <fieldset className="space-y-4">
            <legend className="sr-only">Guided details for this task type</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              {guidedDefs.map((def) => (
                <div key={def.key} className={cn(def.multiline && 'sm:col-span-2')}>
                  <Label htmlFor={`guided-${def.key}`} hint="optional">
                    {def.label}
                  </Label>
                  {def.multiline ? (
                    <Textarea
                      id={`guided-${def.key}`}
                      rows={2}
                      placeholder={def.placeholder}
                      value={guidedValues[def.key] ?? ''}
                      onChange={(e) =>
                        setGuidedValues((g) => ({ ...g, [def.key]: e.target.value }))
                      }
                    />
                  ) : (
                    <Input
                      id={`guided-${def.key}`}
                      placeholder={def.placeholder}
                      value={guidedValues[def.key] ?? ''}
                      onChange={(e) =>
                        setGuidedValues((g) => ({ ...g, [def.key]: e.target.value }))
                      }
                    />
                  )}
                  {def.help && (
                    <p className="mt-1 text-xs text-muted-foreground">{def.help}</p>
                  )}
                </div>
              ))}
            </div>
          </fieldset>
        </CardBody>
      </Card>

      <details className="group rounded-lg border border-border bg-card open:shadow-sm">
        <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold marker:content-none">
          <span aria-hidden="true" className="mr-2 inline-block transition-transform group-open:rotate-90">
            ▸
          </span>
          More spreadsheet context (optional)
        </summary>
        <fieldset className="border-t border-border px-5 pb-5 pt-4">
          <legend className="sr-only">Additional spreadsheet context</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {CONTEXT_FIELDS.map((field) => (
              <div key={field.name} className={cn(field.multiline && 'sm:col-span-2')}>
                <Label htmlFor={`ctx-${field.name}`} hint={field.hint}>
                  {field.label}
                </Label>
                {field.multiline ? (
                  <Textarea
                    id={`ctx-${field.name}`}
                    rows={3}
                    {...register(`context.${field.name}`)}
                  />
                ) : (
                  <Input id={`ctx-${field.name}`} {...register(`context.${field.name}`)} />
                )}
                {fieldError(errors.context?.[field.name]?.message)}
              </div>
            ))}
          </div>
        </fieldset>
      </details>

      <details className="group rounded-lg border border-border bg-card open:shadow-sm">
        <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold marker:content-none">
          <span aria-hidden="true" className="mr-2 inline-block transition-transform group-open:rotate-90">
            ▸
          </span>
          Provider, model &amp; fallback
        </summary>
        <div className="space-y-4 border-t border-border px-5 pb-5 pt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="provider" hint="optional">
                Provider
              </Label>
              <Select id="provider" {...register('provider')}>
                <option value="">Default (from Settings)</option>
                {(configuredProviders ?? []).map((p) => (
                  <option key={p.value} value={p.value} disabled={!p.configured}>
                    {p.label}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-muted-foreground">
                Configure API keys in Settings — they are stored encrypted and never shown again.
              </p>
            </div>
            <div>
              <Label htmlFor="model" hint="optional">
                Model
              </Label>
              <Input
                id="model"
                list="model-options"
                placeholder="Default model for the provider"
                {...register('model')}
              />
              <datalist id="model-options">
                {(modelsQuery.data?.models ?? []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </datalist>
              {modelsQuery.isError && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Model list unavailable — type a model id manually.
                </p>
              )}
            </div>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
              {...register('useFallback')}
            />
            <span>
              <span className="font-medium">Use fallback provider</span> — if the selected provider
              fails (rate limit, outage, bad config), retry on your configured fallback provider.
              The result is clearly labelled “Fallback used”.
            </span>
          </label>

          {attachment && (
            <div className="rounded-md border border-border bg-muted p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm">
                  <span className="font-medium">{attachment.filename}</span>{' '}
                  <span className="text-muted-foreground">(analysed workbook attached)</span>
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    clearAttachment()
                    setAttachment(null)
                  }}
                >
                  Remove
                </Button>
              </div>
              <label className="mt-2 flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                  {...register('includeFileContext')}
                />
                <span>
                  I consent to send the extracted workbook context (sheet names, headers, sample
                  values) to the selected AI provider for this request.
                </span>
              </label>
            </div>
          )}
        </div>
      </details>

      {error && (
        <div role="alert" data-testid="submit-error" className="rounded-lg border border-danger/50 bg-danger/10 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-3">
        <p className="mr-auto text-xs text-muted-foreground">
          sheetJEDI never executes generated code — you stay in control.
        </p>
        <Button type="submit" size="lg" loading={loading} data-testid="generate-button">
          {loading ? 'Generating…' : 'Generate solution'}
        </Button>
      </div>
    </form>
  )
}
