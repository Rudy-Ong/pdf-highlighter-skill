#!/usr/bin/env python3
"""pdfhl - read and highlight PDFs (Zotero-style) from the terminal or a local web viewer.

Run with the project venv:  .venv/bin/python .claude/skills/pdf-highlighter/scripts/pdfhl.py <command> ...

Commands
  serve  [--root DIR ...] [--port 8765]        open the web viewer (annotation list on the left);
                                               default folder: $PDFHL_ROOT or the current directory
  text   FILE.pdf [--page N]                   dump text by page (so you can pick sentences)
  add    FILE.pdf --text "sentence" [--color yellow] [--note "..."] [--page N] [--all]
  list   FILE.pdf [--json]                     list highlights
  remove FILE.pdf --xref N --page N            delete one highlight
  export FILE.pdf [-o out.md]                  highlights + notes as Markdown
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf  # noqa: E402

import annotlib as A  # noqa: E402



def cmd_text(a):
    doc = pymupdf.open(a.file)
    pages = [a.page - 1] if a.page else range(len(doc))
    for i in pages:
        print(f"\n=== Page {i + 1} ===")
        print(doc[i].get_text("text"))


def cmd_add(a):
    A.backup_once(a.file)
    doc = pymupdf.open(a.file)
    hits = A.find_quads(doc, a.text, a.page, max_hits=10_000 if a.all else 1)
    if not hits:
        print("NOT FOUND: " + a.text[:80], file=sys.stderr)
        return 2
    for page_no, quads in hits:
        xref = A.add_highlight(doc, page_no, quads, a.color, a.note or "")
        print(f"highlighted page {page_no} xref {xref}: {a.text[:60]}")
    A.save(doc, a.file)


def cmd_list(a):
    items = A.list_annots(pymupdf.open(a.file))
    if a.json:
        print(json.dumps(items, indent=1, ensure_ascii=False))
        return
    for it in items:
        print(f"p{it['page']:>3} xref {it['xref']:>5} [{it['color']}] {it['text'][:90]}"
              + (f"  // {it['note']}" if it["note"] else ""))
    print(f"{len(items)} highlight(s)")


def cmd_remove(a):
    A.backup_once(a.file)
    doc = pymupdf.open(a.file)
    ok = A.delete_annot(doc, a.page, a.xref)
    if ok:
        A.save(doc, a.file)
    print("removed" if ok else "not found")
    return 0 if ok else 2


def cmd_export(a):
    doc = pymupdf.open(a.file)
    md = A.export_markdown(doc, os.path.basename(a.file))
    if a.output:
        open(a.output, "w", encoding="utf-8").write(md)
        print("wrote", a.output)
    else:
        print(md)


def cmd_serve(a):
    import server
    roots = a.root or [os.environ.get("PDFHL_ROOT") or os.getcwd()]
    server.run(roots, a.port, open_browser=not a.no_browser)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("serve"); s.add_argument("--root", action="append"); s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true"); s.set_defaults(f=cmd_serve)
    s = sp.add_parser("text"); s.add_argument("file"); s.add_argument("--page", type=int); s.set_defaults(f=cmd_text)
    s = sp.add_parser("add"); s.add_argument("file"); s.add_argument("--text", required=True)
    s.add_argument("--color", default="yellow", choices=list(A.COLORS)); s.add_argument("--note")
    s.add_argument("--page", type=int); s.add_argument("--all", action="store_true"); s.set_defaults(f=cmd_add)
    s = sp.add_parser("list"); s.add_argument("file"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_list)
    s = sp.add_parser("remove"); s.add_argument("file"); s.add_argument("--xref", type=int, required=True)
    s.add_argument("--page", type=int, required=True); s.set_defaults(f=cmd_remove)
    s = sp.add_parser("export"); s.add_argument("file"); s.add_argument("-o", "--output"); s.set_defaults(f=cmd_export)
    a = p.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
