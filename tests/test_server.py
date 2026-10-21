"""Unit tests for the EchoWave server helpers and the generated Lite page."""
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


server = _load('echowave_server', 'server.py')
build_lite = _load('echowave_build_lite', 'build_lite.py')


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class TTLCacheTests(unittest.TestCase):
    def test_get_put_and_expiry(self):
        clock = FakeClock()
        cache = server.TTLCache(max_entries=4, ttl=5, clock=clock)
        cache.put('a', {'x': 1})
        self.assertEqual(cache.get('a'), {'x': 1})
        clock.now += 5.1
        self.assertIsNone(cache.get('a'))
        self.assertEqual(len(cache), 0)

    def test_capacity_evicts_oldest(self):
        clock = FakeClock()
        cache = server.TTLCache(max_entries=2, ttl=100, clock=clock)
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)
        self.assertIsNone(cache.get('a'))
        self.assertEqual(cache.get('b'), 2)
        self.assertEqual(cache.get('c'), 3)

    def test_clear(self):
        cache = server.TTLCache(max_entries=2, ttl=100, clock=FakeClock())
        cache.put('a', 1)
        cache.clear()
        self.assertIsNone(cache.get('a'))


class ParamTests(unittest.TestCase):
    def test_limit_default_and_clamp(self):
        self.assertEqual(server.parse_int_param({}, 'limit', 10, 1, 50), 10)
        self.assertEqual(server.parse_int_param({'limit': ['0']}, 'limit', 10, 1, 50), 1)
        self.assertEqual(server.parse_int_param({'limit': ['999']}, 'limit', 10, 1, 50), 50)
        self.assertEqual(server.parse_int_param({'limit': ['abc']}, 'limit', 10, 1, 50), 10)
        self.assertEqual(server.parse_int_param({'limit': ['']}, 'limit', 10, 1, 50), 10)

    def test_page_clamp(self):
        self.assertEqual(server.parse_int_param({'page': ['0']}, 'page', 1, 1, 100), 1)
        self.assertEqual(server.parse_int_param({'page': ['500']}, 'page', 1, 1, 100), 100)

    def test_first_param(self):
        self.assertEqual(server.first_param({'x': ['a', 'b']}, 'x'), 'a')
        self.assertEqual(server.first_param({}, 'x', 'fallback'), 'fallback')


class StaticPathTests(unittest.TestCase):
    def test_index_is_served(self):
        target = server.resolve_static_path('/index.html')
        self.assertIsNotNone(target)
        self.assertEqual(target.name, 'index.html')

    def test_disallowed_suffix(self):
        self.assertIsNone(server.resolve_static_path('/server.py'))
        self.assertIsNone(server.resolve_static_path('/README.md'))

    def test_missing_file(self):
        self.assertIsNone(server.resolve_static_path('/does-not-exist.json'))

    def test_path_traversal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / 'root'
            root.mkdir()
            (root / 'app.json').write_text('{}', encoding='utf-8')
            (tmp_path / 'secret.json').write_text('{}', encoding='utf-8')

            original_root = server.ROOT
            server.ROOT = root
            try:
                self.assertIsNotNone(server.resolve_static_path('/app.json'))
                self.assertIsNone(server.resolve_static_path('/../secret.json'))
                self.assertIsNone(server.resolve_static_path('/sub/../../secret.json'))
            finally:
                server.ROOT = original_root


class CorsTests(unittest.TestCase):
    def test_local_pages_allowed(self):
        for origin in (
            'http://localhost:5000',
            'http://127.0.0.1:8000',
            'https://localhost',
            'null',
        ):
            self.assertEqual(server.allowed_origin(origin), origin)

    def test_official_pages_allowed(self):
        self.assertEqual(
            server.allowed_origin('https://huiihao.github.io'),
            'https://huiihao.github.io',
        )

    def test_other_sites_rejected(self):
        for origin in (
            'https://evil.com',
            'https://evil.github.io',
            'http://localhost.evil.com',
            'nullx',
        ):
            self.assertIsNone(server.allowed_origin(origin))

    def test_non_http_scheme_rejected(self):
        self.assertIsNone(server.allowed_origin('ftp://localhost'))

    def test_missing_origin(self):
        self.assertIsNone(server.allowed_origin(None))
        self.assertIsNone(server.allowed_origin(''))


class SongPayloadTests(unittest.TestCase):
    def test_payload_shape(self):
        class Song:
            identifier = '123'
            song_name = 'Title'
            singers = 'Artist'
            album = 'Album'
            cover_url = 'https://example.com/c.jpg'
            download_url = 'https://example.com/a.mp3'
            lyric = '[00:00]la'
            duration = '03:00'
            ext = 'mp3'

        payload = server._song_payload('netease', Song())
        self.assertEqual(payload['id'], '123')
        self.assertEqual(payload['title'], 'Title')
        self.assertEqual(payload['artist'], 'Artist')
        self.assertEqual(payload['source'], 'netease')
        self.assertEqual(payload['ext'], 'mp3')

    def test_missing_optional_fields(self):
        class Song:
            identifier = None
            song_name = None
            singers = None
            album = None
            cover_url = None
            download_url = None
            lyric = None
            duration = None
            ext = None

        payload = server._song_payload('qq', Song())
        self.assertEqual(payload['id'], '')
        self.assertIsNone(payload['audio_url'])
        self.assertIsNone(payload['cover'])


class _FakeSong:
    def __init__(self, index):
        self.identifier = str(index)
        self.song_name = 'Song %d' % index
        self.singers = 'Artist'
        self.album = 'Album'
        self.cover_url = None
        self.download_url = 'https://example.com/%d.mp3' % index
        self.lyric = None
        self.duration = '00:03:00'
        self.ext = 'mp3'


class _FakeClient:
    def __init__(self):
        self.calls = []

    def search(self, keyword=None, num_threadings=5):
        self.calls.append(keyword)
        return [_FakeSong(i) for i in range(1, 26)]


class _FakeMusicClient:
    def __init__(self):
        self.music_clients = {name: _FakeClient() for name in server.SOURCE_MAP.values()}


class HttpApiTests(unittest.TestCase):
    """Exercise the real HTTP handler with a fake musicdl client."""

    def setUp(self):
        server._mc = _FakeMusicClient()
        server._search_cache.clear()
        server._url_cache.clear()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        server._mc = None
        server._search_cache.clear()
        server._url_cache.clear()

    def get(self, path, origin=None, method='GET'):
        request = Request(self.base + path, method=method)
        if origin:
            request.add_header('Origin', origin)
        return urlopen(request, timeout=5)

    def get_json(self, path, origin=None):
        with self.get(path, origin=origin) as response:
            return response.status, response.headers, json.load(response)

    def test_status(self):
        status, _, body = self.get_json('/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(body['status'], 'ok')
        self.assertTrue(body['ready'])
        self.assertIsInstance(body['available'], bool)
        self.assertEqual(body['version'], server.VERSION)

    def test_search_pagination_and_cache(self):
        status, _, page1 = self.get_json(
            '/api/search?source=netease&keyword=x&limit=10&page=1'
        )
        self.assertEqual(status, 200)
        self.assertEqual(page1['total'], 25)
        self.assertEqual([s['id'] for s in page1['results']], [str(i) for i in range(1, 11)])

        _, _, page2 = self.get_json('/api/search?source=netease&keyword=x&limit=10&page=2')
        self.assertEqual([s['id'] for s in page2['results']], [str(i) for i in range(11, 21)])

        _, _, page3 = self.get_json('/api/search?source=netease&keyword=x&limit=10&page=3')
        self.assertEqual([s['id'] for s in page3['results']], [str(i) for i in range(21, 26)])

        _, _, page4 = self.get_json('/api/search?source=netease&keyword=x&limit=10&page=4')
        self.assertEqual(page4['results'], [])

        client = server._mc.music_clients['NeteaseMusicClient']
        self.assertEqual(client.calls, ['x'])  # all pages served from one cached search

    def test_search_validation(self):
        with self.assertRaises(HTTPError) as bad_source:
            self.get('/api/search?source=nope&keyword=x')
        self.assertEqual(bad_source.exception.code, 400)

        with self.assertRaises(HTTPError) as no_keyword:
            self.get('/api/search?source=netease&keyword=')
        self.assertEqual(no_keyword.exception.code, 400)

        _, _, body = self.get_json(
            '/api/search?source=netease&keyword=x&limit=999&page=0'
        )
        self.assertEqual(body['limit'], server.MAX_LIMIT)
        self.assertEqual(body['page'], 1)

    def test_song_url_lookup(self):
        _, _, body = self.get_json('/api/url?source=netease&id=7')
        self.assertEqual(body['audio_url'], 'https://example.com/7.mp3')

    def test_static_files_and_rejections(self):
        with self.get('/') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'<!DOCTYPE html>', response.read())

        with self.get('/docs/index.html') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'EchoWave Lite', response.read())

        for path in ('/server.py', '/README.md', '/does-not-exist.json'):
            with self.assertRaises(HTTPError) as missing:
                self.get(path)
            self.assertEqual(missing.exception.code, 404)

    def test_cors_allowlist(self):
        _, headers, _ = self.get_json('/api/status', origin='http://localhost:5000')
        self.assertEqual(headers.get('Access-Control-Allow-Origin'), 'http://localhost:5000')

        _, headers, _ = self.get_json('/api/status', origin='https://evil.example')
        self.assertIsNone(headers.get('Access-Control-Allow-Origin'))

    def test_options_preflight(self):
        with self.get('/api/search', origin='https://huiihao.github.io', method='OPTIONS') as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(
                response.headers.get('Access-Control-Allow-Origin'),
                'https://huiihao.github.io',
            )


class LiteBuildTests(unittest.TestCase):
    def test_generated_page_is_current(self):
        expected = build_lite.render((ROOT / 'index.html').read_text(encoding='utf-8'))
        actual = (ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(actual, expected)

    def test_lite_defaults(self):
        text = (ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<title>EchoWave Lite</title>', text)
        self.assertIn('kuwo:false,kugou:false,migu:false', text)
        self.assertNotIn('id="proxy-status"', text)


if __name__ == '__main__':
    unittest.main()
