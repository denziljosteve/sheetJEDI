// Preset navigation, example prompts, and dynamic guided-field definitions.

import type { Platform, SkillLevel, TaskType } from './types'

export interface GuidedFieldDef {
  key: string
  label: string
  placeholder: string
  help?: string
  multiline?: boolean
}

export interface Preset {
  slug: string
  label: string
  short: string
  taskType: TaskType
  platform?: Platform // null = user's choice
  description: string
}

export const PRESETS: Preset[] = [
  {
    slug: 'formula',
    label: 'Formula',
    short: 'Excel / Sheets formulas',
    taskType: 'formula',
    description: 'XLOOKUP, INDEX/MATCH, SUMIFS, ARRAYFORMULA and more.',
  },
  {
    slug: 'vba',
    label: 'VBA macro',
    short: 'Excel VBA',
    taskType: 'vba_macro',
    platform: 'excel',
    description: 'Macros, events, formatting automation and add-ins.',
  },
  {
    slug: 'apps-script',
    label: 'Apps Script',
    short: 'Google Apps Script',
    taskType: 'apps_script',
    platform: 'google_sheets',
    description: 'Triggers, custom menus, integrations for Google Sheets.',
  },
  {
    slug: 'office-script',
    label: 'Office Script',
    short: 'Office Scripts',
    taskType: 'office_script',
    platform: 'excel',
    description: 'TypeScript automation for Excel on the web.',
  },
  {
    slug: 'cleaning',
    label: 'Data cleaning',
    short: 'Clean & transform',
    taskType: 'data_cleaning',
    description: 'Deduplicate, standardise, split and reshape messy data.',
  },
  {
    slug: 'analysis',
    label: 'Analysis',
    short: 'Analyse data',
    taskType: 'data_analysis',
    description: 'Summaries, pivots, aggregations and statistics.',
  },
  {
    slug: 'reporting',
    label: 'Reporting',
    short: 'Build reports',
    taskType: 'reporting',
    description: 'Structured reports, dashboards and recurring digests.',
  },
  {
    slug: 'charts',
    label: 'Charts',
    short: 'Visualise',
    taskType: 'charts',
    description: 'Chart selection, setup and formatting guidance.',
  },
  {
    slug: 'troubleshoot',
    label: 'Troubleshoot',
    short: 'Fix an error',
    taskType: 'troubleshooting',
    description: 'Diagnose #REF!, #VALUE!, #N/A and logic problems.',
  },
]

export function presetBySlug(slug: string | undefined): Preset | null {
  if (!slug) return null
  return PRESETS.find((p) => p.slug === slug) ?? null
}

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  formula: 'Formula',
  vba_macro: 'VBA macro',
  office_script: 'Office Script',
  apps_script: 'Apps Script',
  data_cleaning: 'Data cleaning',
  data_analysis: 'Data analysis',
  reporting: 'Reporting',
  charts: 'Charts',
  troubleshooting: 'Troubleshooting',
  other: 'Other',
}

// Dynamic guided fields per task type (rendered as optional inputs).
export const GUIDED_FIELDS: Record<string, GuidedFieldDef[]> = {
  formula: [
    { key: 'lookup_column', label: 'Lookup column', placeholder: 'e.g. Column A (SKU) or B:B (Region)' },
    { key: 'return_column', label: 'Return column', placeholder: 'e.g. Column D (Price)' },
    { key: 'criteria', label: 'Filter / criteria', placeholder: 'e.g. Status="Shipped" AND Date>=TODAY()-30' },
    { key: 'output_location', label: 'Where the result goes', placeholder: 'e.g. Cell F2 of the summary sheet' },
  ],
  vba_macro: [
    { key: 'target_range', label: 'Target range / sheet', placeholder: 'e.g. Sheet1!A2:H1000' },
    { key: 'macro_action', label: 'What the macro should do', placeholder: 'e.g. highlight rows where total > 10,000', multiline: true },
    { key: 'trigger', label: 'Trigger', placeholder: 'e.g. button click, Workbook_Open, Worksheet_Change' },
    { key: 'output_location', label: 'Output location', placeholder: 'e.g. write results starting in column J' },
  ],
  office_script: [
    { key: 'target_range', label: 'Target range / sheet', placeholder: 'e.g. active sheet, A1:F500' },
    { key: 'script_action', label: 'What the script should do', placeholder: 'e.g. freeze header row, bold it, autosize columns', multiline: true },
    { key: 'parameters', label: 'Parameters / inputs', placeholder: 'e.g. prompt for a date range before running' },
  ],
  apps_script: [
    { key: 'trigger', label: 'Trigger', placeholder: 'e.g. onFormSubmit, time-driven daily, onEdit' },
    { key: 'script_action', label: 'What the script should do', placeholder: 'e.g. append a timestamp and notify by email', multiline: true },
    { key: 'integrations', label: 'Integrations', placeholder: 'e.g. Gmail, Calendar, Slack webhook' },
  ],
  data_cleaning: [
    { key: 'target_columns', label: 'Columns to clean', placeholder: 'e.g. Email, Name, Phone' },
    { key: 'cleaning_operations', label: 'Cleaning operations', placeholder: 'e.g. trim spaces, lowercase emails, remove duplicate rows', multiline: true },
    { key: 'output_location', label: 'Output location', placeholder: 'e.g. new sheet called Cleaned' },
  ],
  data_analysis: [
    { key: 'grouping_column', label: 'Group by', placeholder: 'e.g. Region, Product category' },
    { key: 'metrics', label: 'Metrics', placeholder: 'e.g. total revenue, average order value, order count' },
    { key: 'filters', label: 'Filters', placeholder: 'e.g. only completed orders in 2026' },
  ],
  reporting: [
    { key: 'report_period', label: 'Reporting period', placeholder: 'e.g. monthly, week-over-week' },
    { key: 'metrics', label: 'Key metrics', placeholder: 'e.g. revenue, units, conversion rate' },
    { key: 'audience', label: 'Audience / tone', placeholder: 'e.g. executive summary for leadership' },
  ],
  charts: [
    { key: 'chart_type', label: 'Chart type', placeholder: 'e.g. clustered column, line, combo, pie' },
    { key: 'x_axis', label: 'X axis / categories', placeholder: 'e.g. Month' },
    { key: 'y_axis', label: 'Y axis / values', placeholder: 'e.g. Revenue' },
    { key: 'filters', label: 'Filters', placeholder: 'e.g. top 10 products only' },
  ],
  troubleshooting: [
    { key: 'failing_formula', label: 'Failing formula / code', placeholder: '=SUMIFS(...) or the VBA line', multiline: true },
    { key: 'error_context', label: 'When it happens', placeholder: 'e.g. only on rows below 500, or after copying the sheet' },
    { key: 'expected_behaviour', label: 'Expected behaviour', placeholder: 'e.g. should total only visible filtered rows' },
  ],
  other: [
    { key: 'details', label: 'Extra details', placeholder: 'Anything that describes the outcome you want', multiline: true },
  ],
}

export function guidedFieldsFor(taskType: TaskType): GuidedFieldDef[] {
  return GUIDED_FIELDS[taskType] ?? GUIDED_FIELDS.other
}

export interface ExampleItem {
  label: string
  prompt: string
  taskType: TaskType
  platform: Platform
  guided?: Record<string, string>
}

export const EXAMPLES: Record<string, ExampleItem[]> = {
  formula: [
    {
      label: 'XLOOKUP across sheets',
      prompt:
        'Return the product name from the Products sheet by matching the SKU in column A of my Orders sheet (exact match, "Not found" if missing).',
      taskType: 'formula',
      platform: 'excel',
      guided: { lookup_column: 'Orders!A:A (SKU)', return_column: 'Products!A:B (Name)', output_location: 'Orders!C2 filled down' },
    },
    {
      label: 'SUMIFS with two criteria',
      prompt:
        'Total the Sales column where Region = "West" and the Date is within the current quarter.',
      taskType: 'formula',
      platform: 'excel',
      guided: { criteria: 'Region="West" AND Date in current quarter', output_location: 'Summary!B2' },
    },
    {
      label: 'Google Sheets ARRAYFORMULA',
      prompt:
        'Concatenate first and last name columns with a space for every row automatically using ARRAYFORMULA in Google Sheets.',
      taskType: 'formula',
      platform: 'google_sheets',
      guided: { output_location: 'Column C, one formula at the top' },
    },
  ],
  vba_macro: [
    {
      label: 'Highlight large values',
      prompt:
        'Write a macro that highlights every cell in column B greater than 10,000 in red and adds a comment with the row date.',
      taskType: 'vba_macro',
      platform: 'excel',
      guided: { target_range: 'Column B', trigger: 'Button click' },
    },
    {
      label: 'Auto-fit and export',
      prompt:
        'Macro that auto-fits all columns on the active sheet, then exports the sheet as a PDF to my Documents folder.',
      taskType: 'vba_macro',
      platform: 'excel',
    },
  ],
  'apps-script': [
    {
      label: 'Form submission email',
      prompt:
        'When a Google Form response arrives, timestamp the row and email me a summary of the answers.',
      taskType: 'apps_script',
      platform: 'google_sheets',
      guided: { trigger: 'onFormSubmit' },
    },
    {
      label: 'Custom menu + cleanup',
      prompt:
        'Add a custom menu to my sheet with a "Clean data" item that trims whitespace and removes duplicate rows.',
      taskType: 'apps_script',
      platform: 'google_sheets',
    },
  ],
  'office-script': [
    {
      label: 'Standardise formatting',
      prompt:
        'Standardise the active sheet: freeze the header row, bold it, apply a filter, and autosize all columns.',
      taskType: 'office_script',
      platform: 'excel',
    },
    {
      label: 'Split a column into two',
      prompt:
        'Split the "Full Name" column into "First" and "Last" columns using a space delimiter, shifting other columns right.',
      taskType: 'office_script',
      platform: 'excel',
      guided: { target_range: 'Column A (Full Name)' },
    },
  ],
  cleaning: [
    {
      label: 'Trim and deduplicate',
      prompt:
        'Clean my Customers sheet: trim leading/trailing spaces, lowercase all emails, and remove exact duplicate rows.',
      taskType: 'data_cleaning',
      platform: 'excel',
      guided: { target_columns: 'Name, Email' },
    },
    {
      label: 'Standardise dates',
      prompt:
        'Convert a mixed-date column (text like "5 Jan 24", "2024-01-05", "01/05/2024") into real dates that sort correctly.',
      taskType: 'data_cleaning',
      platform: 'excel',
    },
  ],
  analysis: [
    {
      label: 'Sales by region',
      prompt:
        'Summarise sales by region: total revenue, average order value and order count, sorted descending by revenue.',
      taskType: 'data_analysis',
      platform: 'excel',
      guided: { grouping_column: 'Region', metrics: 'Total revenue, AOV, order count' },
    },
    {
      label: 'Top products',
      prompt: 'Find the top 10 products by units sold this year, with their share of total units.',
      taskType: 'data_analysis',
      platform: 'excel',
    },
  ],
  reporting: [
    {
      label: 'Monthly sales report',
      prompt:
        'Build a monthly sales report: revenue by month, MoM growth %, and a short commentary line for each month.',
      taskType: 'reporting',
      platform: 'excel',
      guided: { report_period: 'monthly', metrics: 'Revenue, MoM growth %' },
    },
  ],
  charts: [
    {
      label: 'Column chart by category',
      prompt:
        'Create a clustered column chart showing units sold per product category for the last 12 months.',
      taskType: 'charts',
      platform: 'excel',
      guided: { chart_type: 'clustered column', x_axis: 'Month', y_axis: 'Units sold' },
    },
  ],
  troubleshoot: [
    {
      label: '#VALUE! in SUMIFS',
      prompt:
        'My SUMIFS returns #VALUE! even though the ranges are the same size. Help me diagnose and fix it.',
      taskType: 'troubleshooting',
      platform: 'excel',
    },
    {
      label: 'VBA runtime error 1004',
      prompt:
        'My VBA macro fails with "Run-time error 1004: Application-defined or object-defined error" when writing to the sheet.',
      taskType: 'troubleshooting',
      platform: 'excel',
    },
  ],
}

export function examplesFor(taskType: TaskType): ExampleItem[] {
  const preset = PRESETS.find((p) => p.taskType === taskType)
  return (preset && EXAMPLES[preset.slug]) || []
}

export const SKILL_LEVELS: { value: SkillLevel; label: string }[] = [
  { value: 'beginner', label: 'Beginner — explain every step' },
  { value: 'intermediate', label: 'Intermediate — concise guidance' },
  { value: 'advanced', label: 'Advanced — technical depth' },
]

export const EXPLANATION_LANGUAGES = [
  'English',
  'Hindi',
  'Spanish',
  'French',
  'German',
  'Portuguese',
  'Arabic',
]
