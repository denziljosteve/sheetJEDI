// TypeScript types mirroring the sheetJEDI backend API contract (api/v1).

export type Platform = 'excel' | 'google_sheets'

export type TaskType =
  | 'formula'
  | 'vba_macro'
  | 'office_script'
  | 'apps_script'
  | 'data_cleaning'
  | 'data_analysis'
  | 'reporting'
  | 'charts'
  | 'troubleshooting'
  | 'other'

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced'

export type ConfigStatus = 'unconfigured' | 'configured' | 'tested' | 'failed'

export interface ProviderCapabilities {
  streaming: boolean
  model_discovery: boolean
  json_mode: boolean
  custom_base_url: boolean
}

export interface ProviderStatus {
  name: string
  display_name: string
  protocol: string
  default_base_url: string
  capabilities: ProviderCapabilities
  status_note: string | null
  verification_status: string
  docs_url: string | null
  config_status: ConfigStatus
  api_key_hint: string | null
  base_url_override: string | null
  default_model: string | null
  timeout_seconds: number | null
  last_tested_at: string | null
  last_test_message: string | null
}

export interface ProviderConfigUpdate {
  api_key?: string | null
  clear_api_key?: boolean
  base_url?: string | null
  default_model?: string | null
  timeout_seconds?: number | null
}

export interface ProviderTestResult {
  provider: string
  ok: boolean
  message: string
  models_count: number | null
  latency_ms: number | null
  tested_at: string
}

export interface ModelInfo {
  id: string
  name: string
  context_window: number | null
  capabilities: Record<string, unknown>
}

export interface ModelListResponse {
  provider: string
  models: ModelInfo[]
  source: 'live' | 'cache'
  fetched_at: string | null
}

export interface AppSettings {
  default_provider: string | null
  default_model: string | null
  fallback_provider: string | null
  fallback_model: string | null
  history_enabled: boolean
  default_platform: Platform
  default_skill_level: SkillLevel
  default_explanation_language: string
}

export interface SpreadsheetContext {
  worksheet_names?: string | null
  column_names?: string | null
  input_data_description?: string | null
  expected_result?: string | null
  constraints?: string | null
  existing_formula_or_code?: string | null
  error_message?: string | null
  sample_data?: string | null
  extra_notes?: string | null
}

export interface GenerationRequest {
  request: string
  platform: Platform
  task_type: TaskType
  task_category?: string | null
  excel_version?: string | null
  sheets_version?: string | null
  skill_level: SkillLevel
  explanation_language: string
  context: SpreadsheetContext
  guided: Record<string, string>
  provider?: string | null
  model?: string | null
  use_fallback: boolean
  file_id?: string | null
  include_file_context: boolean
}

export interface ImplementationStep {
  title: string
  instructions: string
  cell_references: string[]
  code_location: string | null
}

export interface AlternativeSolution {
  title: string
  description: string
  formula: string | null
  code: string | null
  when_to_use: string | null
}

export interface CommonError {
  error: string
  cause: string
  solution: string
}

export interface SolutionResponse {
  title: string
  summary: string
  platform: Platform
  task_type: TaskType
  task_category: string | null
  formula: string | null
  code: string | null
  code_language: string | null
  required_version: string | null
  assumptions: string[]
  prerequisites: string[]
  explanation: string
  implementation_steps: ImplementationStep[]
  example_input: string | null
  expected_output: string | null
  alternative_solutions: AlternativeSolution[]
  common_errors: CommonError[]
  troubleshooting: string[]
  warnings: string[]
  confidence_notes: string | null
}

export interface GenerationResponse {
  solution: SolutionResponse
  solution_id: string | null
  provider: string
  model: string
  fallback_used: boolean
  degraded: boolean
  degraded_notice: string | null
  usage: { prompt_tokens: number | null; completion_tokens: number | null } | null
  generated_at: string
}

export interface ColumnProfile {
  name: string
  inferred_type: 'number' | 'date' | 'text' | 'boolean' | 'mixed' | 'empty'
  non_empty: number
  empty: number
  distinct_sampled: number
  sample_values: string[]
}

export interface SheetProfile {
  name: string
  total_rows_estimate: number | null
  total_columns: number
  scanned_rows: number
  truncated: boolean
  headers: string[]
  columns: ColumnProfile[]
  sample_rows: (string | null)[][]
  duplicate_rows_scanned: number
}

export interface AnalysisRecommendation {
  area: string
  recommendation: string
}

export interface WorkbookAnalysis {
  file_id: string
  filename: string
  file_type: string
  size_bytes: number
  sheet_count: number
  sheets: SheetProfile[]
  recommendations: AnalysisRecommendation[]
  notes: string[]
  analyzed_at: string
}

export interface HistoryItem {
  id: string
  platform: string
  task_type: string
  task_category: string | null
  skill_level: string | null
  title: string | null
  provider: string | null
  model: string | null
  fallback_used: boolean
  created_at: string
  request_preview: string | null
}

export interface HistoryPage {
  items: HistoryItem[]
  total: number
  limit: number
  offset: number
}

export interface SolutionDetail {
  id: string
  platform: string
  task_type: string
  created_at: string
  request: Record<string, unknown>
  solution: SolutionResponse
  provider: string | null
  model: string | null
  fallback_used: boolean
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
    request_id?: string
  }
}
