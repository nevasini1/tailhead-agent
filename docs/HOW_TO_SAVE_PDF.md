# Save documentation as PDF

**Source of truth:** the `.html` files in this folder. They use normal web fonts so PDFs render reliably.

## 1. Manual (no scripts)

1. Open in **Chrome** or **Edge**: `trailhead-agent-project-report.html` or `trailhead-agent-engineering-reference.html`.
2. **Ctrl+P** → **Save as PDF** / **Microsoft Print to PDF**.

## 2. Windows: regenerate `.pdf` from HTML (Edge headless)

From the **repo root**:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\print_docs_to_pdf.ps1
```

Writes:

- `docs/trailhead-agent-project-report.pdf`
- `docs/trailhead-agent-engineering-reference.pdf`

## 3. Optional: Python + fpdf2

Some PDF viewers show **fpdf2** output as a blank page even though text is present. Prefer **HTML + print** or **`print_docs_to_pdf.ps1`** above.

```text
pip install -e ".[docs]"
python scripts/generate_project_report_pdf.py
python scripts/generate_engineering_pdf.py
```

Defaults write under **`docs/fpdf-output/`** so they do **not** overwrite the main **`docs/*.pdf`** files (those come from Edge + HTML).

| Document | HTML | Prebuilt PDF (Edge from HTML) |
|----------|------|-------------------------------|
| Project report | `trailhead-agent-project-report.html` (SVG diagrams, swimlanes, appendix tables) | `trailhead-agent-project-report.pdf` |
| Engineering reference | `trailhead-agent-engineering-reference.html` | `trailhead-agent-engineering-reference.pdf` |
