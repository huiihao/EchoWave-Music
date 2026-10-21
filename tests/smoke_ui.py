"""Headless UI smoke test with mocked upstream music APIs.

Run: python tests/smoke_ui.py
Requires: pip install playwright && playwright install chromium
"""
import base64
import io
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 5099
URL = f'http://127.0.0.1:{PORT}/'

# 8 seconds of silence; long enough that playback does not end mid-test.
_buf = io.BytesIO()
with wave.open(_buf, 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(8000)
    wav.writeframes(b'\x00\x00' * 8000 * 8)
WAV = _buf.getvalue()
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)

counts = {}


def bump(key):
    counts[key] = counts.get(key, 0) + 1


def seed_for(keyword):
    return sum(ord(c) for c in keyword) * 1000


def meting_items(server, page, keyword):
    if page > 2:
        return []
    base = seed_for(keyword) + page * 100
    return [
        {
            'name': f'{server} {keyword} {page}-{i}',
            'artist': f'Artist {i}',
            'url': f'https://api.qijieya.cn/meting/?server={server}&type=url&id={base + i}',
            'pic': f'https://api.qijieya.cn/meting/?server={server}&type=pic&id={base + i}',
            'lrc': f'https://api.qijieya.cn/meting/?type=lrc&id={base + i}',
        }
        for i in range(10)
    ]


def handle_meting(route, request):
    query = parse_qs(urlparse(request.url).query)
    kind = query.get('type', [''])[0]
    if kind == 'search':
        server = query.get('server', ['netease'])[0]
        page = int(query.get('page', ['1'])[0])
        keyword = query.get('id', [''])[0]
        bump(('meting', server, keyword, page))
        body = json.dumps(meting_items(server, page, keyword))
        route.fulfill(status=200, content_type='application/json', body=body)
    elif kind == 'lrc':
        route.fulfill(
            status=200,
            content_type='text/plain; charset=utf-8',
            body='[00:00.00]First line\n[00:02.00]Second line\n[00:04.00]Third line\n',
        )
    elif kind == 'pic':
        route.fulfill(status=200, content_type='image/png', body=PNG)
    elif kind == 'url':
        route.fulfill(status=200, content_type='audio/wav', body=WAV)
    else:
        route.fulfill(status=404, body='')


def handle_qq(route, request):
    query = parse_qs(urlparse(request.url).query)
    if 'mid' in query:
        mid = query['mid'][0]
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'song_title': 'QQ detail',
                'singer_name': 'QQ Artist',
                'album_pic': 'https://api.qijieya.cn/meting/?type=pic&id=1',
                'song_play_url_standard': 'https://api.qijieya.cn/meting/?server=qq&type=url&id=1',
                'song_lyric': '[00:00.00]QQ line',
                'song_mid': mid,
            }),
        )
        return
    bump('qq_search')
    keyword = query.get('msg', [''])[0]
    seed = seed_for(keyword)
    body = json.dumps([
        {
            'song_mid': f'{seed}-mid{i}',
            'song_title': f'QQ {keyword} {i}',
            'singer_name': 'QQ Artist',
            'pay': '免费',
        }
        for i in range(1, 21)
    ])
    route.fulfill(status=200, content_type='application/json', body=body)


def handle_kuwo(route, request):
    query = parse_qs(urlparse(request.url).query)
    if 'id' in query:
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'code': 200,
                'data': {
                    'pic': 'https://api.qijieya.cn/meting/?type=pic&id=2',
                    'url': 'https://api.qijieya.cn/meting/?server=kuwo&type=url&id=2',
                    'lyric': '[00:00.00]Kuwo line',
                },
            }),
        )
        return
    page = int(query.get('page', ['1'])[0])
    keyword = query.get('name', [''])[0]
    bump(('kuwo', keyword, page))
    data = [] if page > 2 else [
        {
            'rid': seed_for(keyword) + page * 100 + i,
            'name': f'Kuwo {keyword} {page}-{i}',
            'artist': 'Kuwo Artist',
            'album': 'Kuwo Album',
            'pic': None,
        }
        for i in range(10)
    ]
    route.fulfill(
        status=200,
        content_type='application/json',
        body=json.dumps({'code': 200, 'data': data}),
    )


def handle_proxy_search(route, request):
    query = parse_qs(urlparse(request.url).query)
    source = query.get('source', [''])[0]
    keyword = query.get('keyword', [''])[0]
    page = int(query.get('page', ['1'])[0])
    limit = int(query.get('limit', ['10'])[0])
    bump(('proxy_search', source, keyword, page))
    results = []
    if page <= 2:
        for i in range(limit):
            n = (page - 1) * limit + i + 1
            results.append({
                'id': f'{keyword}-{n}',
                'title': f'{source} {keyword} {n}',
                'artist': 'Proxy Artist',
                'album': 'Proxy Album',
                'cover': 'https://api.qijieya.cn/meting/?type=pic&id=9',
                'audio_url': None,  # force the /api/url detail lookup
                'lyric': '[00:00.00]Proxy line',
            })
    route.fulfill(
        status=200,
        content_type='application/json',
        body=json.dumps({
            'source': source,
            'keyword': keyword,
            'page': page,
            'limit': limit,
            'total': 20,
            'results': results,
        }),
    )


def handle_proxy_url(route, request):
    query = parse_qs(urlparse(request.url).query)
    source = query.get('source', [''])[0]
    song_id = query.get('id', [''])[0]
    bump(('proxy_url', source))
    route.fulfill(
        status=200,
        content_type='application/json',
        body=json.dumps({
            'source': source,
            'id': song_id,
            'audio_url': 'https://api.qijieya.cn/meting/?server=netease&type=url&id=777',
        }),
    )


def wait_for_server(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(URL + 'api/status', timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError('server did not start')


def main():
    server = subprocess.Popen(
        [sys.executable, 'server.py', '--no-browser', '--port', str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--autoplay-policy=no-user-gesture-required'],
            )
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            console_errors = []
            page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
            page.on('pageerror', lambda exc: console_errors.append(str(exc)))

            page.route(re.compile(r'^https://api\.qijieya\.cn/meting/'), handle_meting)
            page.route(re.compile(r'^https://tang\.api\.s01s\.cn/'), handle_qq)
            page.route(re.compile(r'^https://kw-api\.cenguigui\.cn/'), handle_kuwo)
            page.route(re.compile(r'^https://fonts\.googleapis\.com/'),
                       lambda r, q: r.fulfill(status=200, content_type='text/css', body=''))
            page.route(re.compile(r'^https://fonts\.gstatic\.com/'), lambda r, q: r.abort())
            # Force direct-source mode so the mocked adapters are exercised.
            page.route('**/api/status', lambda r, q: r.fulfill(status=503, body=''))

            page.goto(URL)
            page.wait_for_selector('.source-chip', timeout=10000)

            assert page.title() == 'EchoWave Music', page.title()
            page.wait_for_selector('#proxy-status', state='visible', timeout=5000)
            assert page.locator('.source-chip.checked').count() == 3  # netease, qq, kuwo

            # ── Search page 1 ──
            page.fill('#search-input', 'test')
            page.click('#search-btn')
            page.wait_for_function(
                "document.querySelector('#search-count').textContent === '30 tracks'",
                timeout=10000,
            )
            assert page.locator('#result-grid .result-card').count() == 30
            assert counts.get(('meting', 'netease', 'test', 1)) == 1
            assert counts.get(('kuwo', 'test', 1)) == 1
            assert counts.get('qq_search') == 1

            # ── Infinite scroll: page 2 adds 30, page 3 exhausts ──
            page.eval_on_selector('#search-view', 'el => { el.scrollTop = el.scrollHeight; }')
            page.wait_for_function(
                "document.querySelector('#search-count').textContent === '60 tracks'",
                timeout=10000,
            )
            assert page.locator('#result-grid .result-card').count() == 60

            page.eval_on_selector('#search-view', 'el => { el.scrollTop = el.scrollHeight; }')
            page.wait_for_function(
                "document.querySelector('#search-status').textContent.includes('All results loaded')",
                timeout=10000,
            )
            assert page.locator('#result-grid .result-card').count() == 60
            assert counts.get(('meting', 'netease', 'test', 3)) == 1
            assert counts.get(('kuwo', 'test', 3)) == 1
            assert counts.get('qq_search') == 3

            before = dict(counts)
            page.eval_on_selector(
                '#search-view',
                "el => { el.scrollTop = 0; el.dispatchEvent(new Event('scroll')); el.scrollTop = el.scrollHeight; }",
            )
            page.wait_for_timeout(800)
            assert counts == before, 'loadMore fired again after exhaustion'

            # ── Favorite survives a new search and can be removed ──
            first_card = page.locator('#result-grid .result-card').first
            fav_title = first_card.locator('.card-title').inner_text()
            first_card.locator('button[data-action="fav"]').click()
            assert first_card.locator('button[data-action="fav"]').evaluate(
                "el => el.classList.contains('fav-active')"
            )

            page.fill('#search-input', 'other')
            page.click('#search-btn')
            page.wait_for_function(
                "document.querySelector('#search-count').textContent === '30 tracks'",
                timeout=10000,
            )
            assert 'other' in page.locator('#result-grid .card-title').first.inner_text()
            page.click('.nav-item[data-panel="favorites"]')
            page.wait_for_selector('#playlist-panel.open')
            assert page.locator('#pl-list .pl-item').count() == 1
            assert fav_title in page.locator('#pl-list .pl-item').first.inner_text()
            page.locator('#pl-list .pl-item button[data-action="fav"]').first.click()
            page.wait_for_selector('#pl-list .state-empty', timeout=5000)
            assert page.locator('#sidebar-fav-count').inner_text() == '0'
            page.click('#pl-close-btn')

            # ── Create a playlist through the add-to-playlist flow ──
            page.fill('#search-input', 'test')
            page.click('#search-btn')
            page.wait_for_function(
                "document.querySelector('#search-count').textContent === '30 tracks'",
                timeout=10000,
            )
            page.locator('#result-grid .result-card').first.locator(
                'button[data-action="addpl"]'
            ).click()
            page.wait_for_selector('#new-pl-modal.open')
            page.fill('#new-pl-name', 'Road Trip')
            page.click('#new-pl-confirm-btn')
            page.wait_for_function(
                "document.querySelector('#pl-playlist-select').selectedOptions[0]"
                ".textContent.includes('Road Trip (1)')",
                timeout=5000,
            )

            # Stored tracks omit heavy lyrics and short-lived audio URLs.
            stored = json.loads(page.evaluate("localStorage.getItem('echowave-library-v2')"))
            stored_track = stored['playlists'][0]['tracks'][0]
            assert 'lrc' not in stored_track
            assert 'audioUrl' not in stored_track
            assert stored_track['detailsLoaded'] is False

            # Sidebar "Playlist" must open the real playlists tab, with remove buttons.
            page.click('.nav-item[data-panel="playlists"]')
            page.wait_for_selector('#playlist-panel.open')
            assert page.locator('.pl-tab[data-pltab="playlists"]').evaluate(
                "el => el.classList.contains('active')"
            )
            assert page.locator('#pl-list .pl-item').count() == 1
            assert page.locator('#pl-list .pl-item button[data-action="remove"]').count() == 1
            page.click('#pl-close-btn')

            # ── Play, lyrics, A/B loop ──
            page.locator('#result-grid .result-card').first.click()
            page.wait_for_function(
                "document.querySelector('#np-title').textContent.includes('test')",
                timeout=5000,
            )
            page.wait_for_function(
                "document.querySelector('#audio').paused === false",
                timeout=5000,
            )
            page.wait_for_selector('.np-lyrics-line', timeout=5000)
            assert page.locator('.np-lyrics-line').count() >= 2

            page.click('#np-ab-a-btn')
            page.wait_for_selector('#np-ab-marker-a.active', timeout=3000)
            page.click('#np-ab-b-btn')
            page.wait_for_selector('#np-ab-loop.active', timeout=3000)
            page.click('#np-ab-clear-btn')
            page.wait_for_function(
                "!document.querySelector('#np-ab-loop').classList.contains('active')"
            )

            assert page.locator('#np-lyrics.alt').count() == 0
            page.click('#np-lyricfx-btn')
            assert page.locator('#np-lyrics.alt').count() == 1

            page.wait_for_function(
                "document.querySelector('#audio').currentTime > 0.5",
                timeout=3000,
            )
            page.click('#np-play-btn')
            page.wait_for_function("document.querySelector('#audio').paused === true", timeout=3000)

            page.click('.nav-item[data-view="stats"]')
            page.wait_for_function(
                "document.querySelector('#stat-total-plays').textContent === '1'",
                timeout=5000,
            )
            assert page.locator('#stat-list .stat-row').count() >= 1

            # Resuming a paused track must not add another play.
            assert page.evaluate("document.querySelector('#audio').currentTime") > 0.5
            page.click('.nav-item[data-view="search"]')
            page.locator('#result-grid .result-card').first.click()
            page.wait_for_function(
                "document.querySelector('#audio').paused === false",
                timeout=5000,
            )
            page.wait_for_timeout(300)
            page.click('#np-play-btn')
            page.wait_for_function(
                "document.querySelector('#audio').paused === true",
                timeout=3000,
            )
            page.click('.nav-item[data-view="stats"]')
            assert page.locator('#stat-total-plays').inner_text() == '1'

            # ── Removing the playing track from its playlist clears playback ──
            page.click('.nav-item[data-panel="playlists"]')
            page.wait_for_selector('#playlist-panel.open')
            page.locator('#pl-list .pl-item').first.click()
            page.wait_for_function(
                "document.querySelector('#audio').paused === false",
                timeout=5000,
            )
            assert page.locator('#result-grid .result-card.playing').count() == 1
            page.locator('#pl-list .pl-item button[data-action="remove"]').first.click()
            page.wait_for_function(
                "document.querySelector('#np-title').textContent === 'No Track'"
                " && document.querySelector('#sidebar-mini-title').textContent === 'Not playing'"
                " && document.querySelectorAll('#result-grid .result-card.playing').length === 0",
                timeout=5000,
            )
            assert 'Lyrics will appear here' in page.locator('#np-lyrics').text_content()
            assert page.locator('#pl-list .state-empty').count() == 1
            assert page.locator('#np-time-current').inner_text() == '00:00'
            assert page.locator('#np-time-duration').inner_text() == '00:00'
            assert page.evaluate(
                "document.querySelector('#audio').getAttribute('src')"
            ) is None
            page.click('#pl-close-btn')

            # ── Search history delete does not trigger a search ──
            page.click('.nav-item[data-view="search"]')
            page.fill('#search-input', '')
            page.focus('#search-input')
            page.wait_for_selector('#search-history.open', timeout=3000)
            history_before = page.locator('.search-history-item').count()
            assert history_before >= 2
            status_before = page.locator('#search-status').inner_text()
            page.locator('.search-history-item .sh-delete').first.click()
            page.wait_for_timeout(150)
            assert page.locator('.search-history-item').count() == history_before - 1
            assert page.locator('#search-input').input_value() == ''
            assert page.locator('#search-status').inner_text() == status_before
            page.click('#sh-clear')
            assert page.locator('.search-history-item').count() == 0

            # ── Theme persists across reload ──
            page.click('#theme-toggle-top')
            assert page.evaluate("document.documentElement.dataset.theme") == 'light'
            page.reload()
            page.wait_for_selector('.source-chip', timeout=10000)
            assert page.evaluate("document.documentElement.dataset.theme") == 'light'
            assert page.evaluate("localStorage.getItem('echowave-theme')") == 'light'

            # Playlists survive a reload even though stored tracks are slimmed.
            page.click('.nav-item[data-panel="playlists"]')
            page.wait_for_selector('#playlist-panel.open')
            assert 'Road Trip (0)' in page.locator('#pl-playlist-select').inner_text()
            assert page.locator('#pl-list .state-empty').count() == 1
            page.click('#pl-close-btn')

            # ── No JS errors (the forced 503 proxy probes are expected) ──
            unexpected = [
                e for e in console_errors
                if 'fonts.g' not in e and '503 (Service Unavailable)' not in e
            ]
            assert not unexpected, unexpected
            page.close()

            # ── Proxy mode: status ok, page through /api/search, /api/url ──
            proxy_context = browser.new_context(viewport={'width': 1280, 'height': 800})
            proxy_errors = []
            proxy_context.route(
                re.compile(r'^https://api\.qijieya\.cn/meting/'), handle_meting
            )
            proxy_context.route(re.compile(r'^https://tang\.api\.s01s\.cn/'), handle_qq)
            proxy_context.route(re.compile(r'^https://fonts\.googleapis\.com/'),
                                lambda r, q: r.fulfill(status=200, content_type='text/css', body=''))
            proxy_context.route(re.compile(r'^https://fonts\.gstatic\.com/'), lambda r, q: r.abort())
            proxy_context.route(re.compile(r'/api/search\?'), handle_proxy_search)
            proxy_context.route(re.compile(r'/api/url\?'), handle_proxy_url)
            proxy_context.route(
                '**/api/status',
                lambda r, q: r.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({'status': 'ok', 'sources': [], 'version': '1.2', 'ready': True}),
                ),
            )

            proxy_page = proxy_context.new_page()
            proxy_page.on(
                'console',
                lambda msg: proxy_errors.append(msg.text) if msg.type == 'error' else None,
            )
            proxy_page.on('pageerror', lambda exc: proxy_errors.append(str(exc)))
            proxy_page.goto(URL)
            proxy_page.wait_for_selector('.source-chip', timeout=10000)
            proxy_page.wait_for_function(
                "!document.querySelector('.source-chip.kuwo').textContent.includes('preview')",
                timeout=5000,
            )

            proxy_page.fill('#search-input', 'proxy')
            proxy_page.click('#search-btn')
            proxy_page.wait_for_function(
                "document.querySelector('#search-count').textContent === '30 tracks'",
                timeout=10000,
            )
            assert counts.get(('proxy_search', 'kuwo', 'proxy', 1)) == 1

            proxy_page.eval_on_selector('#search-view', 'el => { el.scrollTop = el.scrollHeight; }')
            proxy_page.wait_for_function(
                "document.querySelector('#search-count').textContent === '60 tracks'",
                timeout=10000,
            )
            assert counts.get(('proxy_search', 'kuwo', 'proxy', 2)) == 1

            proxy_page.eval_on_selector('#search-view', 'el => { el.scrollTop = el.scrollHeight; }')
            proxy_page.wait_for_function(
                "document.querySelector('#search-status').textContent.includes('All results loaded')",
                timeout=10000,
            )
            assert counts.get(('proxy_search', 'kuwo', 'proxy', 3)) == 1

            kuwo_card = proxy_page.locator('#result-grid .result-card[data-uid^="kuwo-"]').first
            assert kuwo_card.count() == 1
            kuwo_card.click()
            proxy_page.wait_for_function(
                "document.querySelector('#np-title').textContent.includes('kuwo proxy')",
                timeout=5000,
            )
            proxy_page.wait_for_function(
                "document.querySelector('#audio').paused === false",
                timeout=5000,
            )
            assert counts.get(('proxy_url', 'kuwo')) == 1
            assert proxy_page.locator('#np-source-badge').text_content().strip() == 'Kuwo'

            proxy_unexpected = [
                e for e in proxy_errors if 'fonts.g' not in e
            ]
            assert not proxy_unexpected, proxy_unexpected
            proxy_context.close()

            browser.close()
        print('UI smoke test passed.')
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == '__main__':
    main()
