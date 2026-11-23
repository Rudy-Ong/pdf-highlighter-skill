"""Tiny local server for the PDF viewer. Binds to 127.0.0.1 only; serves *.pdf under the given roots."""
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pymupdf

import annotlib as A

VIEWER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer", "index.html")
LOCK = threading.Lock()
ROOTS = []


def list_pdfs():
    out = []
    for r in ROOTS:
        for dp, dn, fn in os.walk(r):
            dn[:] = sorted(d for d in dn if not d.startswith("."))
            for f in sorted(fn):
                if f.lower().endswith(".pdf") and not f.startswith("."):
                    full = os.path.join(dp, f)
                    out.append({"name": os.path.relpath(full, r) if len(ROOTS) == 1 else full,
                                "id": full})
    return out


def resolve(pdf_id):
    """Only allow existing .pdf files located under one of the roots (blocks path traversal)."""
    full = os.path.realpath(pdf_id)
    if not full.lower().endswith(".pdf") or not os.path.isfile(full):
        return None
    for r in ROOTS:
        if full.startswith(os.path.realpath(r) + os.sep):
            return full
    return None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _pdf(self, q):
        p = resolve((q.get("id") or [""])[0])
        if not p:
            self._send(404, {"error": "pdf not found"})
        return p

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._send(200, open(VIEWER, "rb").read(), "text/html; charset=utf-8")
        if u.path == "/api/pdfs":
            return self._send(200, list_pdfs())
        p = self._pdf(q) if u.path in ("/pdf", "/api/annots", "/api/export") else None
        if u.path in ("/pdf", "/api/annots", "/api/export") and not p:
            return
        if u.path == "/pdf":
            with LOCK:
                return self._send(200, open(p, "rb").read(), "application/pdf")
        if u.path == "/api/annots":
            with LOCK:
                d = pymupdf.open(p)
                return self._send(200, A.list_annots(d))
        if u.path == "/api/export":
            with LOCK:
                md = A.export_markdown(pymupdf.open(p), os.path.basename(p))
            return self._send(200, md, "text/markdown; charset=utf-8")
        self._send(404, {"error": "not found"})

    def _mutate(self, fn):
        b = self._body() if self.command != "DELETE" else {}
        q = parse_qs(urlparse(self.path).query)
        pid = b.get("id") or (q.get("id") or [""])[0]
        p = resolve(pid)
        if not p:
            return self._send(404, {"error": "pdf not found"})
        with LOCK:
            A.backup_once(p)
            doc = pymupdf.open(p)
            try:
                res = fn(doc, b, q)
                if res is None:
                    return self._send(404, {"error": "annotation not found"})
                A.save(doc, p)
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": str(e)})
        self._send(200, res)

    def do_POST(self):
        def add(doc, b, q):
            page = doc[int(b["page"]) - 1]
            quads = A.quads_from_fractions(page, b["rects"])
            if not quads:
                return None
            return {"xref": A.add_highlight(doc, int(b["page"]), quads, b.get("color", "yellow"), b.get("note", ""))}
        if urlparse(self.path).path == "/api/annots":
            return self._mutate(add)
        self._send(404, {"error": "not found"})

    def do_PATCH(self):
        def upd(doc, b, q):
            ok = A.update_annot(doc, int(b["page"]), int(b["xref"]), b.get("note"), b.get("color"))
            return {"ok": True} if ok else None
        if urlparse(self.path).path == "/api/annots":
            return self._mutate(upd)
        self._send(404, {"error": "not found"})

    def do_DELETE(self):
        def rm(doc, b, q):
            ok = A.delete_annot(doc, int(q["page"][0]), int(q["xref"][0]))
            return {"ok": True} if ok else None
        if urlparse(self.path).path == "/api/annots":
            return self._mutate(rm)
        self._send(404, {"error": "not found"})


def run(roots, port=8765, open_browser=True):
    ROOTS[:] = [os.path.realpath(os.path.expanduser(r)) for r in roots]
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"PDF highlighter on {url}\n  roots: {ROOTS}\n  Ctrl+C to stop", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
