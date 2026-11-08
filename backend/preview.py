"""Separate synthetic preview server. No database or API is loaded."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from .runtime import development_only

class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        development_only()
        if self.path.split('?')[0] == '/auth-client.js':
            content = b'globalThis.ACE_SYNTHETIC_PREVIEW = true;'
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()

if __name__ == '__main__':
    development_only()
    directory = str(Path(__file__).resolve().parent.parent / 'frontend')
    HTTPServer(('127.0.0.1', 8081), partial(PreviewHandler, directory=directory)).serve_forever()
