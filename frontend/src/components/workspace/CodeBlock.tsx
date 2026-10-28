import Editor, { loader, type OnMount } from '@monaco-editor/react'
import { useEffect, useMemo, useState } from 'react'
import { useTheme } from '../../hooks/useTheme'
import { CopyButton } from '../CopyButton'

interface CodeBlockProps {
  code: string
  language?: string
  readOnly?: boolean
  height?: string
  label?: string
}

const LANGUAGE_ALIASES: Record<string, string> = {
  vba: 'vb',
  vb: 'vb',
  vbnet: 'vb',
  'visual basic': 'vb',
  office_script: 'typescript',
  office_scripts: 'typescript',
  apps_script: 'javascript',
  google_apps_script: 'javascript',
  javascript: 'javascript',
  typescript: 'typescript',
  python: 'python',
  formula: 'plaintext',
  excel_formula: 'plaintext',
  google_sheets_formula: 'plaintext',
  unvalidated_output: 'plaintext',
  csv: 'plaintext',
  text: 'plaintext',
}

function resolveLanguage(language: string | null | undefined): string {
  if (!language) return 'plaintext'
  const key = language.toLowerCase().trim()
  return LANGUAGE_ALIASES[key] ?? key
}

/**
 * Monaco normally loads from a CDN; if it cannot (offline, blocked), we fall
 * back to a plain read-only <pre> so the code is always visible and copyable.
 */
export function CodeBlock({ code, language, readOnly = true, height, label }: CodeBlockProps) {
  const { theme } = useTheme()
  const resolved = resolveLanguage(language)
  const lineCount = code.split('\n').length
  const autoHeight = height ?? `${Math.min(480, Math.max(120, lineCount * 20 + 40))}px`
  const [monacoState, setMonacoState] = useState<'loading' | 'ready' | 'failed'>('loading')

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      if (!cancelled) setMonacoState((s) => (s === 'loading' ? 'failed' : s))
    }, 8000)
    loader
      .init()
      .then(() => {
        if (cancelled) return
        window.clearTimeout(timer)
        setMonacoState('ready')
      })
      .catch(() => {
        if (cancelled) return
        window.clearTimeout(timer)
        setMonacoState('failed')
      })
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  const handleMount: OnMount = (editor, monaco) => {
    // Escape then Tab moves focus out of the embedded editor (keyboard access).
    editor.addCommand(monaco.KeyCode.Escape, () => {
      editor.getDomNode()?.focus()
    })
  }

  const plainFallback = useMemo(
    () => (
      <pre
        className="overflow-x-auto rounded-md border border-border bg-muted p-4 text-xs leading-relaxed"
        data-testid="code-fallback"
      >
        <code>{code}</code>
      </pre>
    ),
    [code],
  )

  return (
    <div className="group relative" data-testid="code-block">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label ?? resolved}
        </span>
        <CopyButton text={code} label="Copy code" />
      </div>

      {monacoState === 'ready' ? (
        <div className="overflow-hidden rounded-md border border-border" style={{ height: autoHeight }}>
          <Editor
            height={autoHeight}
            language={resolved}
            value={code}
            theme={theme === 'dark' ? 'vs-dark' : 'light'}
            options={{
              readOnly,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontSize: 13,
              wordWrap: 'on',
              renderLineHighlight: 'none',
              overviewRulerLanes: 0,
              guides: { indentation: false },
              folding: lineCount > 30,
              tabSize: 2,
              accessibilitySupport: 'on',
            }}
            loading={
              <div className="flex h-full items-center justify-center bg-muted">
                <span className="text-xs text-muted-foreground">Loading editor…</span>
              </div>
            }
            onMount={handleMount}
          />
        </div>
      ) : (
        plainFallback
      )}

      <p className="mt-1 text-xs text-muted-foreground">
        {monacoState === 'ready' ? (
          <>
            Press <kbd className="rounded border border-border px-1">Esc</kbd> then{' '}
            <kbd className="rounded border border-border px-1">Tab</kbd> to leave the editor.
          </>
        ) : (
          'Read-only view — use Copy code to grab the snippet.'
        )}
      </p>
    </div>
  )
}
