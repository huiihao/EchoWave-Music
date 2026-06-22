"""
EchoWave Music — All-in-One Server
Serves frontend + music proxy. Just run: python server.py
"""
import sys, os, json, threading, time, webbrowser, mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 5000
ROOT = Path(__file__).parent

# ── musicdl lazy init ──────────────────────────────────
mc = None
mc_lock = threading.Lock()
SOURCE_MAP = {
    'netease': 'NeteaseMusicClient', 'qq': 'QQMusicClient',
    'kuwo': 'KuwoMusicClient', 'kugou': 'KugouMusicClient',
    'migu': 'MiguMusicClient',
}

def get_music_client():
    global mc
    if mc is not None: return mc
    with mc_lock:
        if mc is not None: return mc
        from musicdl.musicdl import MusicClient
        cfg = {}
        for name in SOURCE_MAP.values():
            cfg[name] = {'search_size_per_source': 10, 'disable_print': True}
        mc = MusicClient(music_sources=list(SOURCE_MAP.values()), init_music_clients_cfg=cfg)
        return mc

# ── HTTP Handler ───────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _send(self, body, status=200, ct='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = parse_qs(parsed.query)

        # ── Static files ──
        if path == '/' or path == '/index.html':
            fp = ROOT / 'index.html'
            if fp.exists():
                self._send(fp.read_bytes(), ct='text/html; charset=utf-8')
            else:
                self._send({'error': 'index.html not found'}, 404)
            return

        if path.endswith(('.js','.css','.png','.jpg','.gif','.svg','.ico','.json')):
            fp = ROOT / path.lstrip('/')
            if fp.exists() and fp.is_file():
                ct = mimetypes.guess_type(str(fp))[0] or 'application/octet-stream'
                self._send(fp.read_bytes(), ct=ct)
            else:
                self._send({'error': 'not found'}, 404)
            return

        # ── API: status ──
        if path == '/api/status':
            try:
                c = get_music_client()
                self._send({'status': 'ok', 'sources': list(SOURCE_MAP.keys()), 'version': '1.0'})
            except Exception as e:
                self._send({'status': 'error', 'message': str(e)}, 500)

        # ── API: search ──
        elif path == '/api/search':
            source = params.get('source', [None])[0]
            keyword = params.get('keyword', [''])[0]
            limit = int(params.get('limit', ['10'])[0])
            if not source or source not in SOURCE_MAP:
                self._send({'error': f'Invalid source: {source}'}, 400)
                return
            try:
                c = get_music_client()
                client_name = SOURCE_MAP[source]
                results = c.music_clients[client_name].search(keyword=keyword, num_threadings=5)
                songs = []
                for s in results:
                    songs.append({
                        'id': s.identifier or '',
                        'title': s.song_name or '',
                        'artist': s.singers or '',
                        'album': s.album or '',
                        'cover': s.cover_url or None,
                        'audio_url': str(s.download_url) if s.download_url else None,
                        'lyric': s.lyric or None,
                        'duration': s.duration or '',
                        'ext': s.ext or '',
                        'source': source,
                    })
                self._send({'source': source, 'keyword': keyword, 'results': songs})
            except Exception as e:
                import traceback
                self._send({'error': str(e), 'traceback': traceback.format_exc()}, 500)

        # ── API: url ──
        elif path == '/api/url':
            source = params.get('source', [None])[0]
            song_id = params.get('id', [''])[0]
            if not source or source not in SOURCE_MAP:
                self._send({'error': f'Invalid source: {source}'}, 400)
                return
            try:
                c = get_music_client()
                client_name = SOURCE_MAP[source]
                results = c.music_clients[client_name].search(keyword=song_id, num_threadings=3)
                url = None
                for s in results:
                    if str(s.identifier) == song_id or song_id in str(s.identifier):
                        url = str(s.download_url) if s.download_url else None
                        break
                if not url and results:
                    url = str(results[0].download_url) if results[0].download_url else None
                self._send({'source': source, 'id': song_id, 'audio_url': url})
            except Exception as e:
                self._send({'error': str(e)}, 500)

        else:
            self._send({'error': 'Not found'}, 404)

# ── Main ───────────────────────────────────────────────
if __name__ == '__main__':
    if '--port' in sys.argv:
        try: PORT = int(sys.argv[sys.argv.index('--port') + 1])
        except: pass

    server = HTTPServer(('127.0.0.1', PORT), Handler)
    url = f'http://localhost:{PORT}'

    print('  ========================================')
    print('  EchoWave Music Platform')
    print('  ========================================')
    print(f'  Server: {url}')
    print(f'  Press Ctrl+C to stop')
    print('  ----------------------------------------')

    # Pre-warm musicdl in background
    def prewarm():
        print('  Initializing music engines...')
        try:
            get_music_client()
            print('  All 6 sources ready')
        except Exception as e:
            print(f'  Warning: {e}')

    threading.Thread(target=prewarm, daemon=True).start()

    # Open browser
    def open_browser():
        time.sleep(1)
        webbrowser.open(url)
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Shutting down...')
        server.shutdown()
