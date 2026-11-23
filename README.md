# pdf-highlighter

A [Claude Code](https://claude.com/claude-code) skill + small local app for reading papers and highlighting sentences, Zotero-style.

- **Web viewer**: annotation list on the left (notes, colours, jump-to, delete), the PDF on the right. Select text and pick a colour or press `1`–`5`.
- **CLI**: dump text, add/list/remove highlights, export to Markdown. Claude uses this to highlight key sentences for you.
- Highlights are stored **inside the PDF** as standard `/Highlight` annotations, so Zotero, Preview and Acrobat show them too. A pristine copy is kept in `.pdf_highlighter_backup/` before the first edit.

## Install
```bash
git clone https://github.com/Rudy-Ong/pdf-highlighter-skill ~/.claude/skills/pdf-highlighter
python3 -m venv ~/.claude/skills/pdf-highlighter/.venv
~/.claude/skills/pdf-highlighter/.venv/bin/pip install -r ~/.claude/skills/pdf-highlighter/requirements.txt
```

## Use
```bash
PY=~/.claude/skills/pdf-highlighter/.venv/bin/python
HL=~/.claude/skills/pdf-highlighter/scripts/pdfhl.py
$PY $HL serve --root /path/to/pdfs              # http://127.0.0.1:8765/
$PY $HL text paper.pdf --page 1
$PY $HL add paper.pdf --text "exact sentence" --color green --note "key idea"
$PY $HL list paper.pdf
$PY $HL export paper.pdf -o notes.md
```
Or just ask Claude: *"read paper.pdf and highlight the research question, method and main result"*.

## Notes
- Text-based PDFs only. The viewer loads pdf.js 3.11.174 from cdnjs (needs internet). The server listens on `127.0.0.1` only and serves only `.pdf` files under `--root`.
- Depends on [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0 / commercial). It is installed separately, not bundled; check its licence if you redistribute a combined work.
- This repo's own code is MIT-licensed.
