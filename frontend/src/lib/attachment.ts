// Session-scoped hand-off of an analysed workbook between the Analyzer page
// and the workspace (only ids/names are stored, never file contents).

export interface Attachment {
  file_id: string
  filename: string
}

const ATTACHMENT_KEY = 'sheetjedi-attachment'

export function readAttachment(): Attachment | null {
  try {
    const raw = window.sessionStorage.getItem(ATTACHMENT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Attachment
    return parsed && parsed.file_id && parsed.filename ? parsed : null
  } catch {
    return null
  }
}

export function writeAttachment(attachment: Attachment): void {
  try {
    window.sessionStorage.setItem(ATTACHMENT_KEY, JSON.stringify(attachment))
  } catch {
    // Session storage unavailable; attachment simply won't persist.
  }
}

export function clearAttachment(): void {
  try {
    window.sessionStorage.removeItem(ATTACHMENT_KEY)
  } catch {
    // Ignore storage failures.
  }
}
