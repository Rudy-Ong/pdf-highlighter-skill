---
name: pdf-highlighter
description: Read papers and highlight sentences in PDFs, Zotero-style. Use when the user wants to open a PDF reader with an annotation list on the left, highlight or annotate sentences in a paper, have Claude highlight key sentences (claims, methods, results, limitations) in a PDF, list/export highlights and notes, or remove highlights. Highlights are saved as standard annotations inside the PDF.
---

# PDF highlighter

Highlights are written **into the PDF itself** as native `/Highlight` annotations (PyMuPDF), so they also show in Zotero, Preview and Acrobat. The first edit of a PDF stores an untouched copy in `.pdf_highlighter_backup/` next to it.

All commands need Python 3.9+ with PyMuPDF (`pip install pymupdf`, ideally in a venv). Set once:

```
PY=python3                      # or path/to/.venv/bin/python
HL=<this skill folder>/scripts/pdfhl.py   # e.g. ~/.claude/skills/pdf-highlighter/scripts/pdfhl.py
```

## 1. Read and highlight yourself (web viewer)

```
$PY $HL serve --root "/path/to/folder/with/pdfs"
```
Opens http://127.0.0.1:8765/ (local only). Left: PDF picker, filter box, colour palette, and the list of highlights with editable notes (click one to jump to it; Delete removes it). Right: the paper.
- Select text, then click a colour dot in the pop-up, or press **1–5** (yellow, red, green, blue, purple).
- Esc clears the selection. **Export .md** downloads highlights + notes as Markdown.
- Run it in the background (`run_in_background`) if you start it for the user, then tell them the URL. Stop with Ctrl+C / TaskStop.

## 2. Have Claude highlight sentences (CLI)

1. Read the paper: `$PY $HL text paper.pdf [--page N]` (prints `=== Page N ===` sections).
2. Choose sentences that match what the user asked (e.g. research question, method, key result, limitation).
3. Highlight each, copying the sentence text **verbatim** from step 1 (matching ignores case, punctuation and line breaks):
   ```
   $PY $HL add paper.pdf --text "We propose a native-reference coordinate geometry…" --color green --note "core idea"
   ```
   Options: `--page N` to restrict, `--all` to mark every occurrence. Exit code 2 / `NOT FOUND` means the text was not matched; re-copy a shorter exact span.
4. Suggested colour code (tell the user, they can change it): yellow = claim/contribution, green = method, blue = result, red = limitation/problem, purple = definition or idea to cite.
5. Verify with `$PY $HL list paper.pdf`.

Other commands: `list [--json]`, `remove --page N --xref N`, `export paper.pdf [-o notes.md]`.

## Notes and limits
- Only text-based PDFs (scanned images have no text to select).
- Highlights made while the viewer is open appear after the page reloads the PDF (the viewer does this automatically after each change).
- Never edit PDFs outside the folder the user named. Path traversal outside `--root` is refused by the server.
- The viewer loads pdf.js 3.11.174 from cdnjs.cloudflare.com, so it needs internet access.
