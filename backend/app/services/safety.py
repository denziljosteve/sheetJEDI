"""Heuristic safety scanning of generated formulas and code.

Generated code is untrusted. This module flags destructive or data-moving
operations so the UI can warn the user before they run anything. It never
executes generated code — it only pattern-scans text.
"""

from __future__ import annotations

import re

_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "vba": [
        (r"\.\s*Delete\b", "Deletes rows/columns/ranges permanently."),
        (r"\.\s*Clear(Contents|Formats)?\b", "Clears cell contents or formats."),
        (r"\bKill\b\s+", "Deletes files from disk."),
        (r"FileSystemObject.{0,40}(Delete|Move)", "Deletes or moves files on disk."),
        (r"\.\s*SaveAs\b", "Saves the workbook under a new name/location (may overwrite)."),
        (r"\bWorkbooks\.Open\b", "Opens another workbook (external file access)."),
        (r"(?i)(SendMail|MailEnvelope|Outlook|\.Send\b)", "Sends email or data externally."),
        (r"(?i)(\.PasteSpecial|CommandLine|Shell\b)", "Invokes shell or special paste operations."),
    ],
    "office_script": [
        (
            r"\.\s*delete(Sheet|Row|Column|Range|Rows|Columns)?\s*\(",
            "Deletes sheets, rows, columns, or ranges.",
        ),
        (r"\.\s*clear(Contents|Formats)?\s*\(", "Clears cell contents or formats."),
        (r"\.\s*setValues?\s*\(", "Overwrites cell values (check the target range)."),
    ],
    "apps_script": [
        (r"\.\s*deleteSheet\b", "Deletes a sheet."),
        (r"\.\s*deleteRow(s)?\s*\(", "Deletes rows permanently."),
        (r"\.\s*clear\s*\(", "Clears a range of data."),
        (r"UrlFetchApp\.fetch", "Sends data to an external web service."),
        (r"GmailApp\.|MailApp\.", "Sends email."),
        (r"\.\s*flush\s*\(", "Forces pending writes to save."),
    ],
    "formula": [
        (r"(?i)\bWEBSERVICE\s*\(", "Fetches data from an external URL."),
        (r"(?i)\bIMPORT(DATA|XML|HTML)\s*\(", "Imports external web data into the sheet."),
        (r"(?i)\bIMPORTRANGE\s*\(", "Pulls data from another spreadsheet (requires access grant)."),
    ],
}

_LANG_ALIAS = {
    "vba_macro": "vba",
    "office_script": "office_script",
    "apps_script": "apps_script",
    "formula": "formula",
}


def scan_artifact(formula: str | None, code: str | None, code_language: str | None) -> list[str]:
    """Return human-readable warnings for risky constructs found in the output."""
    warnings: list[str] = []

    if code:
        lang = _LANG_ALIAS.get((code_language or "").lower(), (code_language or "").lower())
        patterns = _PATTERNS.get(lang, _PATTERNS["vba"] if lang == "vba" else [])
        for pattern, description in patterns:
            if re.search(pattern, code):
                warnings.append(
                    f"Potentially destructive operation detected: {description} "
                    "Test on a copy of your workbook first and review the code before running."
                )

    if formula:
        for pattern, description in _PATTERNS["formula"]:
            if re.search(pattern, formula):
                warnings.append(f"Data/privacy note: {description}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique
