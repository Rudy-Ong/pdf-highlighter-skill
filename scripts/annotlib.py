"""Shared helpers: read / write native PDF highlight annotations with PyMuPDF.

Highlights are stored *inside the PDF* as standard /Highlight annotations, so Zotero,
Preview, Acrobat, Okular ... all show them. Nothing is kept in a side database.
"""
import os
import re
import shutil

import pymupdf

COLORS = {
    "yellow": (1.0, 0.84, 0.0),
    "red": (1.0, 0.35, 0.35),
    "green": (0.35, 0.8, 0.4),
    "blue": (0.4, 0.7, 1.0),
    "purple": (0.75, 0.55, 1.0),
}
AUTHOR = "pdf-highlighter"


def nearest_color(rgb):
    if not rgb:
        return "yellow"
    return min(COLORS, key=lambda n: sum((a - b) ** 2 for a, b in zip(COLORS[n], rgb)))


def backup_once(path):
    """Keep one untouched copy of the original PDF before the first edit."""
    d = os.path.join(os.path.dirname(path), ".pdf_highlighter_backup")
    dst = os.path.join(d, os.path.basename(path))
    if not os.path.exists(dst):
        os.makedirs(d, exist_ok=True)
        shutil.copy2(path, dst)


def save(doc, path):
    """Incremental save (fast, keeps the original bytes intact); full rewrite as fallback."""
    try:
        doc.saveIncr()
    except Exception:
        tmp = path + ".tmp"
        doc.save(tmp, garbage=0, deflate=True)
        doc.close()
        os.replace(tmp, path)


def _norm(s):
    return re.sub(r"[\W_]+", "", s.lower())


def _quad_rects(annot):
    v = annot.vertices or []
    return [pymupdf.Quad(v[i:i + 4]).rect for i in range(0, len(v) - 3, 4)]


def _words_in(page, rect):
    out = []
    for w in page.get_text("words"):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        if rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 <= cy <= rect.y1:
            out.append(w[4])
    return out


def annot_text(page, annot):
    parts = [" ".join(_words_in(page, r)) for r in _quad_rects(annot)]
    return " ".join(p for p in parts if p).strip()


def list_annots(doc):
    res = []
    for page in doc:
        pw, ph = page.rect.width, page.rect.height
        for a in page.annots() or []:
            if a.type[0] != pymupdf.PDF_ANNOT_HIGHLIGHT:
                continue
            rects = []
            for r in _quad_rects(a):
                d = r * page.rotation_matrix  # unrotated -> displayed space
                rects.append([d.x0 / pw, d.y0 / ph, d.x1 / pw, d.y1 / ph])
            res.append({
                "page": page.number + 1,
                "xref": a.xref,
                "color": nearest_color(a.colors.get("stroke")),
                "note": a.info.get("content", ""),
                "text": annot_text(page, a),
                "rects": rects,
                "author": a.info.get("title", ""),
            })
    return res


def add_highlight(doc, page_no, quads, color="yellow", note=""):
    page = doc[page_no - 1]
    a = page.add_highlight_annot(quads=quads)
    a.set_colors(stroke=COLORS.get(color, COLORS["yellow"]))
    a.set_opacity(0.45)
    a.set_info(content=note or "", title=AUTHOR)
    a.update()
    return a.xref


def quads_from_fractions(page, rects):
    """Fractional rects (0..1 of the displayed page) -> quads in the unrotated page space."""
    pw, ph = page.rect.width, page.rect.height
    out = []
    for x0, y0, x1, y1 in rects:
        r = pymupdf.Rect(x0 * pw, y0 * ph, x1 * pw, y1 * ph) * page.derotation_matrix
        out.append(r.quad)
    return out


def _find_annot(doc, page_no, xref):
    page = doc[page_no - 1]
    for a in page.annots() or []:
        if a.xref == xref:
            return page, a
    return page, None


def update_annot(doc, page_no, xref, note=None, color=None):
    page, a = _find_annot(doc, page_no, xref)
    if a is None:
        return False
    if color in COLORS:
        a.set_colors(stroke=COLORS[color])
    if note is not None:
        a.set_info(content=note, title=AUTHOR)
    a.update()
    return True


def delete_annot(doc, page_no, xref):
    page, a = _find_annot(doc, page_no, xref)
    if a is None:
        return False
    page.delete_annot(a)
    return True


def find_quads(doc, needle, page_no=None, max_hits=1):
    """Locate `needle` (a sentence) in the PDF. Matching ignores case, punctuation and line breaks.

    Returns [(page_no, [Quad, ...])]; one entry per occurrence, one quad per text line.
    """
    toks = [t for t in (_norm(w) for w in needle.split()) if t]
    if not toks:
        return []
    hits = []
    pages = [page_no - 1] if page_no else range(len(doc))
    for pi in pages:
        page = doc[pi]
        words = [w for w in page.get_text("words") if _norm(w[4])]
        norms = [_norm(w[4]) for w in words]
        n = len(toks)
        i = 0
        while i + n <= len(norms):
            if norms[i:i + n] == toks:
                span = words[i:i + n]
                lines = {}
                for w in span:
                    lines.setdefault((w[5], w[6]), []).append(w)
                quads = []
                for ws in lines.values():
                    r = pymupdf.Rect(min(w[0] for w in ws), min(w[1] for w in ws),
                                     max(w[2] for w in ws), max(w[3] for w in ws))
                    quads.append(r.quad)
                hits.append((pi + 1, quads))
                if len(hits) >= max_hits:
                    return hits
                i += n
            else:
                i += 1
        if not hits_for_page(hits, pi + 1):
            # fallback: PyMuPDF's own search (handles hyphenated line breaks better)
            q = page.search_for(needle, quads=True)
            if q:
                hits.append((pi + 1, q))
                if len(hits) >= max_hits:
                    return hits
    return hits


def hits_for_page(hits, p):
    return any(h[0] == p for h in hits)


def export_markdown(doc, name):
    title = (doc.metadata or {}).get("title") or name
    lines = [f"# Highlights: {title}", f"_File: {name}_", ""]
    emoji = {"yellow": "🟨", "red": "🟥", "green": "🟩", "blue": "🟦", "purple": "🟪"}
    items = sorted(list_annots(doc), key=lambda a: (a["page"], a["rects"][0][1] if a["rects"] else 0))
    page = None
    for a in items:
        if a["page"] != page:
            page = a["page"]
            lines += [f"## Page {page}", ""]
        lines.append(f"- {emoji.get(a['color'], '')} “{a['text']}”")
        if a["note"]:
            lines.append(f"  - **Note:** {a['note']}")
    if not items:
        lines.append("_No highlights._")
    return "\n".join(lines) + "\n"
