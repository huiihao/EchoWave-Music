"""
EchoWave Music — All-in-One Server
Serves the frontend and a music proxy. Run: python server.py
"""
import argparse
import importlib.util
import json
import mimetypes
import os
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
VERSION = '1.2'
DEFAULT_PORT = 5000
MAX_LIMIT = 50

SOURCE_MAP = {
    'netease': 'NeteaseMusicClient',
    'qq': 'QQMusicClient',
    'kuwo': 'KuwoMusicClient',
    'kugou': 'KugouMusicClient',
    'migu': 'MiguMusicClient',
}

# Only these file types may be served as static files.
STATIC_SUFFIXES = {
    '.html', '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
    '.ico', '.json', '.webp', '.woff', '.woff2', '.ttf',
}


def env_int(name, default, minimum=1, maximum=100):
    """Read an integer env var, falling back to `default` when invalid."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


SEARCH_SIZE = env_int('ECHOWAVE_SEARCH_SIZE', 30)
CACHE_TTL = env_int('ECHOWAVE_CACHE_TTL', 300, 1, 86400)
EXTRA_ORIGINS = {
    origin.strip().lower()
    for origin in os.environ.get('ECHOWAVE_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
}

try:
    MUSICDL_AVAILABLE = importlib.util.find_spec('musicdl') is not None
except (ImportError, ValueError):
    MUSICDL_AVAILABLE = False


class TTLCache:
    """Small thread-safe TTL cache with a fixed capacity.

    Values are shared between threads: callers must treat them as read-only.
    """

    def __init__(self, max_entries=128, ttl=300.0, clock=time.monotonic):
        self._data = {}
        self._lock = threading.Lock()
        self._max = max_entries
        self._ttl = ttl
        self._clock = clock

    def get(self, key):
        now = self._clock()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= now:
                del self._data[key]
                return None
            return value

    def put(self, key, value):
        now = self._clock()
        with self._lock:
            expired = [k for k, (expires, _) in self._data.items() if expires <= now]
            for k in expired:
                del self._data[k]
            while len(self._data) >= self._max:
                del self._data[next(iter(self._data))]
            self._data[key] = (now + self._ttl, value)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self):
        with self._lock:
            return len(self._data)


# ── musicdl lazy init ──────────────────────────────────
_mc = None
_mc_lock = threading.Lock()
_source_locks = {name: threading.Lock() for name in SOURCE_MAP}
_search_cache = TTLCache(max_entries=64, ttl=CACHE_TTL)
_url_cache = TTLCache(max_entries=256, ttl=CACHE_TTL * 2)


def get_music_client():
    global _mc
    if _mc is not None:
        return _mc
    with _mc_lock:
        if _mc is None:
            from musicdl.musicdl import MusicClient
            cfg = {
                name: {
                    'search_size_per_source': SEARCH_SIZE,
                    'disable_print': True,
                }
                for name in SOURCE_MAP.values()
            }
            _mc = MusicClient(
                music_sources=list(SOURCE_MAP.values()),
                init_music_clients_cfg=cfg,
            )
        return _mc


def _song_payload(source, song):
    """Convert a musicdl song object into the JSON shape the frontend expects."""
    return {
        'id': song.identifier or '',
        'title': song.song_name or '',
        'artist': song.singers or '',
        'album': song.album or '',
        'cover': song.cover_url or None,
        'audio_url': str(song.download_url) if song.download_url else None,
        'lyric': song.lyric or None,
        'duration': song.duration or '',
        'ext': song.ext or '',
        'source': source,
    }


def search_songs(source, keyword):
    """Return the full cached result list for a source/keyword pair."""
    key = (source, keyword)
    cached = _search_cache.get(key)
    if cached is not None:
        return cached

    client_name = SOURCE_MAP[source]
    client = get_music_client().music_clients[client_name]
    # musicdl clients use internal threads; keep one search per source at a time.
    with _source_locks[source]:
        cached = _search_cache.get(key)  # another thread may have filled it
        if cached is not None:
            return cached
        results = client.search(keyword=keyword, num_threadings=5) or []
        songs = [_song_payload(source, song) for song in results]
        _search_cache.put(key, songs)
    return songs


def find_song_url(source, song_id):
    """Look up a playable URL for an already-known song identifier."""
    key = (source, song_id)
    cached = _url_cache.get(key)
    if cached is not None:
        return cached['url']

    client_name = SOURCE_MAP[source]
    client = get_music_client().music_clients[client_name]
    with _source_locks[source]:
        cached = _url_cache.get(key)
        if cached is not None:
            return cached['url']
        results = client.search(keyword=song_id, num_threadings=3) or []

        match = next(
            (song for song in results if str(song.identifier or '') == song_id), None
        )
        if match is None:
            match = next(
                (song for song in results
                 if song.identifier and song_id in str(song.identifier)),
                None,
            )
        if match is None and results:
            match = results[0]
        url = str(match.download_url) if match and match.download_url else None

        # Cache misses too: a song with no playable URL should not be re-searched.
        _url_cache.put(key, {'url': url})
    return url


# ── Request helpers ────────────────────────────────────
def first_param(params, name, default=''):
    values = params.get(name)
    return values[0] if values else default


def parse_int_param(params, name, default, minimum, maximum):
    try:
        value = int(first_param(params, name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def resolve_static_path(url_path):
    """Resolve a URL path to a file inside ROOT, or return None.

    Rejects path traversal, unsupported extensions and missing files.
    """
    relative = url_path.lstrip('/')
    if not relative:
        return None
    target = (ROOT / relative).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return None
    if target.suffix.lower() not in STATIC_SUFFIXES or not target.is_file():
        return None
    return target


def allowed_origin(origin):
    """Return the Origin value when it may read the local proxy, else None.

    The proxy is unauthenticated and bound to localhost. Browser pages on
    localhost, the official GitHub Pages site and the optional
    ECHOWAVE_ALLOWED_ORIGINS list may read it; other websites may not.
    Forks hosted elsewhere should add their origin to
    ECHOWAVE_ALLOWED_ORIGINS instead of allowing every ``*.github.io`` page.
    """
    if not origin:
        return None
    if origin == 'null':  # pages opened from disk
        return origin
    try:
        parsed = urlparse(origin)
        host = (parsed.hostname or '').lower()
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https'):
        return None
    if host in ('localhost', '127.0.0.1', '::1', 'huiihao.github.io'):
        return origin
    if origin.lower() in EXTRA_ORIGINS:
        return origin
    return None


# ── HTTP Handler ───────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = 'EchoWave/' + VERSION
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        pass

    def _send(self, body, status=200, ct='application/json; charset=utf-8', cache='no-store'):
        data = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False, default=str
        ).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        origin = allowed_origin(self.headers.get('Origin'))
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, payload, status=200):
        self._send(payload, status=status)

    def do_OPTIONS(self):
        self.send_response(204)
        origin = allowed_origin(self.headers.get('Origin'))
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Max-Age', '86400')
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        try:
            self._route()
        except Exception:
            traceback.print_exc()
            try:
                self._send_json({'error': 'Internal server error'}, 500)
            except Exception:
                pass

    def _route(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = parse_qs(parsed.query)

        # ── Static files ──
        if path in ('/', '/index.html'):
            self._send_file(ROOT / 'index.html')
            return
        if path in ('/lite', '/lite.html'):
            self._send_file(ROOT / 'docs' / 'index.html')
            return
        if '.' in path.rsplit('/', 1)[-1]:
            target = resolve_static_path(path)
            if target is None:
                self._send_json({'error': 'Not found'}, 404)
            else:
                self._send_file(target)
            return

        # ── API: status ──
        if path == '/api/status':
            # Answer immediately; musicdl initialization runs in the prewarm
            # thread (or lazily on the first search).
            self._send_json({
                'status': 'ok',
                'sources': list(SOURCE_MAP),
                'version': VERSION,
                'available': MUSICDL_AVAILABLE,
                'ready': _mc is not None,
            })

        # ── API: search ──
        elif path == '/api/search':
            source = first_param(params, 'source').lower()
            keyword = first_param(params, 'keyword').strip()
            if source not in SOURCE_MAP:
                self._send_json({'error': 'Invalid source: %s' % source}, 400)
                return
            if not keyword:
                self._send_json({'error': 'Missing keyword'}, 400)
                return

            limit = parse_int_param(params, 'limit', 10, 1, MAX_LIMIT)
            page = parse_int_param(params, 'page', 1, 1, 100)
            songs = search_songs(source, keyword)
            start = (page - 1) * limit
            self._send_json({
                'source': source,
                'keyword': keyword,
                'page': page,
                'limit': limit,
                'total': len(songs),
                'results': songs[start:start + limit],
            })

        # ── API: url ──
        elif path == '/api/url':
            source = first_param(params, 'source').lower()
            song_id = first_param(params, 'id').strip()
            if source not in SOURCE_MAP:
                self._send_json({'error': 'Invalid source: %s' % source}, 400)
                return
            if not song_id:
                self._send_json({'error': 'Missing id'}, 400)
                return
            try:
                url = find_song_url(source, song_id)
                self._send_json({'source': source, 'id': song_id, 'audio_url': url})
            except Exception:
                traceback.print_exc()
                self._send_json({'error': 'Upstream lookup failed'}, 500)

        else:
            self._send_json({'error': 'Not found'}, 404)

    def _send_file(self, file_path):
        if not file_path.is_file():
            self._send_json({'error': 'Not found'}, 404)
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
        if content_type.startswith('text/') or content_type in (
            'application/javascript', 'application/json',
        ):
            content_type += '; charset=utf-8'
        cache = 'no-cache' if content_type.startswith('text/html') else 'public, max-age=3600'
        self._send(file_path.read_bytes(), ct=content_type, cache=cache)


# ── Main ───────────────────────────────────────────────
def parse_args(argv=None):
    default_port = env_int('ECHOWAVE_PORT', DEFAULT_PORT, 1, 65535)
    parser = argparse.ArgumentParser(description='EchoWave Music server')
    parser.add_argument(
        '--port', type=int, default=default_port,
        help=f'port to listen on (default: {default_port})',
    )
    parser.add_argument('--no-browser', action='store_true', help="don't open a browser")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as exc:
        print(f'  Cannot start on port {args.port}: {exc}')
        print(f'  Try: python server.py --port {args.port + 1}')
        return 1
    server.daemon_threads = True
    url = f'http://localhost:{args.port}'

    print('  ========================================')
    print(f'  EchoWave Music Platform  v{VERSION}')
    print('  ========================================')
    print(f'  Server:  {url}')
    print(f'  Sources: {" / ".join(SOURCE_MAP)}')
    print('  Press Ctrl+C to stop')
    print('  ----------------------------------------')

    def prewarm():
        if not MUSICDL_AVAILABLE:
            print('  Warning: musicdl is not installed.')
            print('  Run: pip install -r requirements.txt')
            return
        print('  Initializing music engines...')
        try:
            get_music_client()
            print(f'  All {len(SOURCE_MAP)} sources ready')
        except Exception as exc:
            print(f'  Warning: {exc}')

    threading.Thread(target=prewarm, daemon=True).start()

    if not args.no_browser:
        def open_browser():
            time.sleep(1)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Shutting down...')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
