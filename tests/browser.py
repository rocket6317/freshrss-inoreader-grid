#!/usr/bin/env python3
"""Local-only integration checks using installed FreshRSS functions and synthetic articles.

Requires Chromium and Python's websocket-client (test tools only; no runtime dependency).
Never authenticates, reads real articles, or changes FreshRSS configuration.
"""
import base64
import json
import os
import shutil
import socket
import sys
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = os.environ.get('FRESHRSS_CONTAINER', 'freshrss')
CHROMIUM = os.environ.get('CHROMIUM_BINARY') or shutil.which('chromium') or shutil.which('google-chrome') or shutil.which('chromium-browser')
if not CHROMIUM:
    raise SystemExit('Chromium is required; set CHROMIUM_BINARY to its executable path.')


def installed(path):
    return subprocess.check_output(['docker', 'exec', CONTAINER, 'cat', path]).decode()


main = installed('p/scripts/main.js')
native = main[main.index('const pending_entries ='):main.index('function next_unread_entry(')]
native += main[main.index('function toggle_aside_click('):main.index('function init_nav_menu(')]
native += main[main.index('function collapse_entry('):main.index('function toggle_media(')]
# Use the installed core delegation handler, including native read/bookmark/content links.
native += main[main.index('function init_stream('):main.index('function toggleClass(')]

setup = """
const context = {current_view:'normal', does_lazyload:true, auto_mark_scroll:true,
 auto_remove_article:true, auto_mark_article:false, auto_mark_focus:false,
 sticky_post:true, anonymous:false, csrf:'synthetic-test-token', icons:{}};
function onScroll() {} function incUnreadsFeed() {} function incUnreadsTag() {}
function faviconNbUnread() {} function toggle_bigMarkAsRead_button() {}
function badAjax() { throw Error('Unexpected native request failure'); }
function xmlHttpRequestJson(req) { return req.response; }
window.nativeRequests=[];
window.fetch=async (url, options) => {
 nativeRequests.push({kind:'read',url,body:JSON.parse(options.body)});
 return {ok:true,json:async()=>({})};
};
window.XMLHttpRequest=class {
 open(method,url) {this.url=url;} setRequestHeader() {}
 send(body) { nativeRequests.push({kind:'bookmark',url:this.url,body:JSON.parse(body)});
 this.status=200; this.response={url:this.url,icon:''}; this.onload(); }
};
function article(id) {
 const node=document.createElement('div');
 node.className='flux not_read'; node.id='flux_'+id;
 node.dataset.entry=id; node.dataset.link='https://example.invalid/article/'+id;
 node.innerHTML=`<ul class="horizontal-list flux_header" data-website-name="Science &amp; Design">
 <li class="item titleAuthorSummaryDate"><a class="item-element title" href="https://example.invalid/${id}">A considered headline for article ${id}</a>
 <time datetime="2026-10-17T10:00:00Z">17 October 2026</time></li>
 <li><a class="bookmark" href="/?c=entry&amp;a=bookmark&amp;id=${id}">Save</a></li></ul>
 <article class="flux_content"><div class="content"><header><h1 class="title"><a class="go_website" href="https://example.invalid/${id}">Article ${id}</a></h1></header>
 <div class="text"><span class="ig-entry-meta" hidden data-image="${id%2 ? '/art.svg' : ''}" data-date="17 Oct" data-datetime="2026-10-17T10:00:00Z"></span>
 <button class="ai-summary-btn">Summarize</button><div class="summary-state">Existing summary</div>
 <h2>Story details</h2><p>Sample article content. This is synthetic text, never a private feed.</p>
 ${'<p>Readable content with enough length to verify scrolling and layout.</p>'.repeat(20)}
 <img data-original="/art.svg" alt="" width="500" height="180"></div></div>
 <footer><ul class="horizontal-list bottom"><li><a class="read" href="/?c=entry&amp;a=read&amp;id=${id}">Read</a></li></ul></footer></article>`;
 return node;
}
function initFixture(){
 const stream=document.querySelector('#stream');
 for(let i=1;i<=24;i++) stream.append(article(i));
 init_stream(stream);
 document.querySelector('#nav_menu_toggle_aside button').onclick=()=>toggle_aside_click();
 document.addEventListener('click',event=>{
  if(event.target.matches('.ai-summary-btn')) event.target.nextElementSibling.textContent='Summary updated';
 });
 document.addEventListener('keydown',event=>{
  if(event.key==='j') next_entry(false);
  if(event.key==='c') collapse_entry();
 });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initFixture);
else initFixture();
"""

assets = {
    '/grid.js': ('text/javascript', (ROOT / 'static/grid.js').read_bytes()),
    '/grid.css': ('text/css', (ROOT / 'static/grid.css').read_bytes()),
    '/native.js': ('text/javascript', (setup + native + "\ndocument.dispatchEvent(new Event('freshrss:globalContextLoaded'));\n").encode()),
    '/frss.css': ('text/css', installed('p/themes/base-theme/frss.css').encode()),
    '/adark.css': ('text/css', installed('p/themes/Alternative-Dark/adark.css').encode()),
    '/art.svg': ('image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="360"><rect width="600" height="360" fill="#497f9b"/><circle cx="420" cy="120" r="70" fill="#ddd2ad"/></svg>'),
    '/': ('text/html', b'''<!doctype html><html class="theme_Alternative-Dark" lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="stylesheet" href="/frss.css"><link rel="stylesheet" href="/adark.css">
<link rel="stylesheet" href="/grid.css">
<script defer src="/native.js"></script><script defer src="/grid.js"></script></head>
<body class="normal"><div id="global"><aside class="aside aside_feed"></aside>
<nav class="nav_menu"><div id="nav_menu_toggle_aside"><button>Feeds</button></div><a class="fixture-native-label" href="#news">News</a><button class="btn btn-important fixture-native-action">Action</button></nav>
<main id="stream" class="normal hide_posts"></main></div>
<nav id="nav_entries"><button class="previous_entry">Left</button><button class="up">Up</button><button class="next_entry">Right</button></nav>
</body></html>''')
}
# Editorial screenshots are separate from the deliberately minimal test fixture.
if '--screenshots' in sys.argv:
    demo = ROOT / 'docs/demo'
    demo_core = setup[:setup.index('function article(id)')] + native
    assets['/demo-core.js'] = ('text/javascript', demo_core.encode())
    assets['/demo.js'] = ('text/javascript', (
        'window.demoArticles=' + (demo / 'articles.json').read_text() + ';\n' +
        (demo / 'demo.js').read_text()).encode())
    for photo in (demo / 'images').glob('*.jpg'):
        assets['/demo/images/' + photo.name] = ('image/jpeg', photo.read_bytes())
    assets['/demo'] = ('text/html', assets['/'][1]
        .replace(b'<script defer src="/native.js"></script>',
                 b'<script defer src="/demo-core.js"></script><script defer src="/demo.js"></script>')
        .replace(b'<button>Feeds</button>', b'<button aria-label="Open feed navigation">&#9776;</button>')
        .replace(b'<button class="btn btn-important fixture-native-action">Action</button>',
                 b'<span class="demo-label">8 stories &middot; Editorial demo</span>')
        .replace(b'</head>', b'<style>.nav_menu {display:flex;align-items:center;gap:18px;min-height:60px;box-sizing:border-box}.demo-label {margin-left:auto;font:12px system-ui;opacity:.65;padding-right:12px}.fixture-native-label {font:650 17px system-ui}.nav_menu #nav_menu_toggle_aside {position:static!important;width:44px;flex:0 0 44px;margin:0}.nav_menu>.fixture-native-label {position:static!important;margin:0}#nav_menu_toggle_aside button {font-size:20px;min-width:44px;min-height:44px}@media(max-width:600px){.demo-label{font-size:10px}.nav_menu{gap:12px}}</style></head>'))

assets['/late'] = (assets['/'][0], assets['/'][1].replace(
    b'<script defer src="/native.js"></script><script defer src="/grid.js"></script>',
    b'<script defer src="/grid.js"></script><script async src="/native-late.js"></script>'))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/native-late.js':
            time.sleep(.25)
            item = assets['/native.js']
        else:
            item = assets.get(self.path)
        self.send_response(200 if item else 404)
        self.send_header('Content-Type', item[0] if item else 'text/plain')
        self.end_headers()
        self.wfile.write(item[1] if item else b'')

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
browser = subprocess.Popen([CHROMIUM, '--headless', '--no-sandbox', '--disable-gpu',
    '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    f'--remote-debugging-port={port}', '--remote-allow-origins=*',
    f'--user-data-dir=/tmp/inoreader-grid-test-{int(time.time())}', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws = None
try:
    for _ in range(100):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1))
            break
        except OSError:
            time.sleep(.1)
    else:
        raise RuntimeError('Chromium did not start')
    tab = next(tab for tab in tabs if tab['type'] == 'page' and tab['url'] == 'about:blank')
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15)
    serial = 0
    errors = []

    def command(method, params=None):
        global serial
        serial += 1
        request_id = serial
        ws.send(json.dumps({'id': request_id, 'method': method, 'params': params or {}}))
        while True:
            result = json.loads(ws.recv())
            if result.get('method') == 'Fetch.requestPaused':
                # Resolution fixtures never contact publishers: fulfill image requests locally.
                paused = result['params']
                failed = '/s1200f/0_Fail.jpg' in paused['request']['url']
                serial += 1
                ws.send(json.dumps({'id': serial, 'method': 'Fetch.fulfillRequest', 'params': {
                    'requestId': paused['requestId'], 'responseCode': 404 if failed else 200,
                    'responseHeaders': [{'name': 'Content-Type', 'value': 'image/svg+xml'}],
                    'body': base64.b64encode(b'' if failed else assets['/art.svg'][1]).decode(),
                }}))
                continue
            if result.get('method') == 'Runtime.exceptionThrown':
                errors.append(result['params']['exceptionDetails'])
            if result.get('id') == request_id:
                if 'error' in result:
                    raise RuntimeError(result['error'])
                return result.get('result', {})

    def evaluate(code):
        result = command('Runtime.evaluate', {'expression': code, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def check(code, label):
        assert evaluate(code), (label, errors)
        print('PASS', label, flush=True)

    def settle():
        evaluate('new Promise(resolve=>setTimeout(resolve,100))')

    def gesture(points, cancel=False, hold=0):
        for index, (x, y) in enumerate(points):
            command('Input.dispatchTouchEvent', {'type': 'touchStart' if index == 0 else 'touchMove',
                'touchPoints': [{'id': 1, 'x': x, 'y': y}]})
        if hold:
            time.sleep(hold)
        command('Input.dispatchTouchEvent', {'type': 'touchCancel' if cancel else 'touchEnd', 'touchPoints': []})
        settle()

    def screenshot(name):
        if '--screenshots' not in sys.argv:
            return
        folder = ROOT / 'docs/screenshots'
        folder.mkdir(parents=True, exist_ok=True)
        result = command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
        (folder / name).write_bytes(base64.b64decode(result['data']))

    command('Runtime.enable')
    command('Page.enable')
    command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
    command('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/'})
    for _ in range(100):
        if evaluate("document.querySelectorAll('.ig-card').length===24"):
            break
        time.sleep(.05)
    check("document.querySelectorAll('.ig-card').length===24", 'initial article enhancement')
    check("getComputedStyle(document.querySelector('.ig-title')).color==='rgb(168, 168, 168)' && getComputedStyle(document.querySelector('.fixture-native-label')).color==='rgb(168, 168, 168)'", 'muted text actually renders on cards and native navigation')
    check("getComputedStyle(document.body).backgroundColor==='rgb(25, 25, 25)' && getComputedStyle(document.querySelector('.flux')).backgroundColor==='rgb(36, 36, 36)' && getComputedStyle(document.querySelector('.ig-source')).color==='rgb(160, 160, 160)' && getComputedStyle(document.querySelector('.fixture-native-action')).backgroundColor==='rgb(58, 58, 58)'", 'neutral grey palette renders on surfaces, accents and native actions')
    check("getComputedStyle(document.querySelector('#stream')).gridTemplateColumns.split(' ').length===4", 'four desktop columns with the native FreshRSS theme')
    check("document.documentElement.scrollWidth<=innerWidth", 'desktop has no horizontal overflow')
    check("!context.auto_mark_scroll && !context.auto_remove_article", 'page-local scroll/removal protection')
    evaluate("window.scrollTo(0,700); window.beforeY=scrollY; window.contentNode=document.querySelector('#flux_9 > .flux_content'); document.querySelector('#flux_9 .ig-card').click()")
    settle()
    check("document.querySelector('dialog').open && contentNode===document.querySelector('dialog .flux_content')", 'modal uses original article DOM')
    check("document.querySelector('dialog').closest('.flux').id==='flux_9'", 'native article ancestry retained')
    check("['h1.title a','.text h2','.text p'].every(s=>getComputedStyle(document.querySelector('dialog '+s)).color==='rgb(168, 168, 168)')", 'muted text actually renders on reader titles, native headings and article text')
    check("document.querySelector('dialog .text img').getAttribute('src')==='/art.svg'", 'native lazy media loading')
    evaluate("document.querySelector('dialog .ai-summary-btn').click()")
    check("document.querySelector('dialog .summary-state').textContent==='Summary updated'", 'existing delegated extension button remains functional')
    evaluate("document.querySelector('dialog [aria-label=\"Save article\"]').click()")
    settle()
    check("document.querySelector('#flux_9').classList.contains('favorite') && nativeRequests.some(r=>r.kind==='bookmark' && r.body._csrf==='synthetic-test-token')", 'native bookmark request and state synchronisation')
    evaluate("document.querySelector('dialog [aria-label=\"Mark read\"]').click()")
    settle()
    check("!document.querySelector('#flux_9').classList.contains('not_read')", 'native mark-read request')
    evaluate("document.querySelector('dialog [aria-label=\"Mark unread\"]').click()")
    settle()
    check("document.querySelector('#flux_9').classList.contains('not_read')", 'native mark-unread request')
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))")
    settle()
    check("document.querySelector('dialog[open]').closest('.flux').id==='flux_10'", 'next via keyboard arrow')
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}))")
    settle()
    check("document.querySelector('dialog[open]').closest('.flux').id==='flux_9' && contentNode===document.querySelector('dialog .flux_content')", 'previous restores same article and summary state')
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    settle()
    check("!document.querySelector('dialog[open]') && contentNode===document.querySelector('#flux_9 > .flux_content') && Math.abs(scrollY-beforeY)<2", 'Escape restores DOM and exact grid scroll')
    check("document.activeElement===document.querySelector('#flux_9 .ig-card')", 'focus returns to opening card')
    evaluate("document.querySelector('#stream').append(article(25))")
    settle()
    check("document.querySelector('#flux_25.ig-ready .ig-card')!==null", 'dynamically appended article enhanced')
    evaluate("document.querySelector('#flux_25 .ig-card').click()")
    settle()
    check("document.querySelector('dialog[open] .ig-progress').textContent==='25 / 25' && document.querySelector('dialog [aria-label^=\"Next article\"]').disabled", 'dynamic article navigation and boundary')
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));")
    settle()
    evaluate("document.querySelector('#flux_1 .ig-card').click()")
    settle()
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'j',bubbles:true}))")
    settle()
    check("document.querySelector('dialog[open]').closest('.flux').id==='flux_2'", 'native next-entry shortcut still works')
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'c',bubbles:true}))")
    settle()
    check("!document.querySelector('dialog[open]')", 'native collapse shortcut closes reader')
    for width, columns in [(768, 2), (430, 2), (390, 1), (320, 1)]:
        command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        settle()
        check(f"getComputedStyle(document.querySelector('#stream')).gridTemplateColumns.split(' ').length==={columns} && document.documentElement.scrollWidth<=innerWidth", f'{width}px responsive columns and no overflow')
        check("getComputedStyle(document.querySelector('#nav_entries')).display==='none'", f'{width}px native bottom arrow bar stays hidden despite mobile theme override')
        evaluate("document.querySelector('#flux_1 .ig-card').click()")
        settle()
        if width <= 600:
            check("Math.abs(document.querySelector('dialog').getBoundingClientRect().width-innerWidth)<2 && Math.abs(document.querySelector('dialog').getBoundingClientRect().height-innerHeight)<2", f'{width}px full-screen reader')
        check("Array.from(document.querySelectorAll('dialog .ig-control')).every(n=>n.getBoundingClientRect().height>=44)", f'{width}px touch target sizes')
        evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        settle()
    command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
    command('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 2})
    evaluate("window.swipeBeforeY=scrollY;window.swipeContent=document.querySelector('#flux_1 > .flux_content');document.querySelector('#flux_1 .ig-card').click();document.querySelector('.ig-reader-body').scrollTop=100")
    settle()
    gesture([(12, 600), (13, 550), (14, 450), (14, 350)])
    check("document.querySelector('dialog').open && document.querySelector('.ig-reader-body').scrollTop>100", 'vertical swipe at left edge scrolls article without closing it')
    gesture([(12, 450), (35, 450), (55, 450)])
    check("document.querySelector('dialog').open && !document.querySelector('.ig-swiping')", 'short edge swipe cancels and keeps reader open')
    gesture([(120, 450), (170, 450), (230, 450), (290, 450)])
    check("document.querySelector('dialog').open", 'horizontal swipe away from left edge does not dismiss reader')
    gesture([(35, 450), (20, 450), (1, 450)])
    check("document.querySelector('dialog').open", 'leftward edge swipe does not dismiss reader')
    code_point = evaluate("(()=>{const pre=document.createElement('pre');pre.id='fixture-swipe-code';pre.textContent='Long code sample '.repeat(100);document.querySelector('dialog .text').append(pre);pre.scrollIntoView({block:'center'});pre.scrollLeft=250;const r=pre.getBoundingClientRect();return {x:r.left+10,y:r.top+r.height/2};})()")
    gesture([(code_point['x'], code_point['y']), (code_point['x'] + 60, code_point['y']), (code_point['x'] + 130, code_point['y'])])
    check("document.querySelector('dialog').open && document.querySelector('#fixture-swipe-code').scrollLeft<250", 'horizontal code scrolling remains native even when starting near left edge')
    evaluate("document.querySelector('#fixture-swipe-code').remove()")
    control = evaluate("(()=>{const r=document.querySelector('dialog .ig-control').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    gesture([(control['x'], control['y']), (control['x'] + 55, control['y']), (control['x'] + 130, control['y'])])
    check("document.querySelector('dialog').open", 'gestures on reader controls do not dismiss reader')
    command('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'id': 1, 'x': 12, 'y': 450}, {'id': 2, 'x': 130, 'y': 450}]})
    command('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'id': 1, 'x': 130, 'y': 450}, {'id': 2, 'x': 248, 'y': 450}]})
    command('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    settle()
    check("document.querySelector('dialog').open", 'two-finger gesture does not dismiss reader')
    gesture([(12, 450), (45, 450), (70, 450)], cancel=True)
    check("document.querySelector('dialog').open && !document.querySelector('.ig-swiping') && !document.querySelector('dialog').style.getPropertyValue('--ig-swipe-offset')", 'cancelled touch resets the reader gesture')
    evaluate("document.querySelector('.ig-reader-body').scrollTop=300")
    gesture([(12, 450), (45, 450), (100, 450), (160, 450)])
    check("!document.querySelector('dialog[open]') && swipeContent===document.querySelector('#flux_1 > .flux_content') && Math.abs(scrollY-swipeBeforeY)<2 && document.activeElement===document.querySelector('#flux_1 .ig-card')", 'rightward left-edge swipe closes scrolled reader and restores card, focus and grid scroll')
    evaluate("document.querySelector('#flux_1 .ig-card').click()")
    settle()
    gesture([(52, 450), (108, 450)])
    check("!document.querySelector('dialog[open]') && document.activeElement===document.querySelector('#flux_1 .ig-card')", 'quick short flick closes reader from the wider left-edge area')
    evaluate("document.querySelector('#flux_1 .ig-card').click()")
    settle()
    gesture([(12, 450), (30, 450), (52, 450), (68, 450)], hold=.4)
    check("document.querySelector('dialog').open && !document.querySelector('.ig-swiping')", 'short drag held before release does not count as a quick flick')
    gesture([(12, 450), (28, 450), (56, 450), (88, 450)], hold=.4)
    check("!document.querySelector('dialog[open]') && Math.abs(scrollY-swipeBeforeY)<2", 'deliberate shorter drag closes reader without needing flick speed')
    evaluate("document.querySelector('#flux_1 .ig-card').click()")
    settle()
    gesture([(12, 450), (32, 470), (80, 510)])
    check("document.querySelector('dialog').open", 'diagonal article scrolling does not become a flick dismissal')
    evaluate("document.querySelector('dialog').close()")
    settle()
    command('Emulation.setTouchEmulationEnabled', {'enabled': False})
    check("!document.querySelector('.aside').classList.contains('visible')", 'sidebar starts collapsed')
    evaluate("document.querySelector('#nav_menu_toggle_aside button').click()")
    check("document.querySelector('.aside').classList.contains('visible') && getComputedStyle(document.querySelector('.aside')).display!=='none'", 'native sidebar navigation opens')
    for width in [1440, 390, 320]:
        command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': width < 600})
        settle()
        check("(()=>{const n=document.querySelector('.ig-sidebar-close'),r=n.getBoundingClientRect(); return r.width>=44 && r.height>=44 && r.top>=0 && r.bottom<=innerHeight && n.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));})()", f'{width}px sidebar close button visible and reachable')
        point = evaluate("(()=>{const r=document.querySelector('.ig-sidebar-close').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
        command('Input.dispatchMouseEvent', {'type': 'mousePressed', 'button': 'left', 'clickCount': 1, **point})
        command('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'button': 'left', 'clickCount': 1, **point})
        settle()
        check("!document.querySelector('.aside').classList.contains('visible') && document.querySelector('#nav_menu_toggle_aside button').getAttribute('aria-expanded')==='false' && document.activeElement===document.querySelector('#nav_menu_toggle_aside button')", f'{width}px sidebar close click restores collapsed state and focus')
        evaluate("document.querySelector('#nav_menu_toggle_aside button').click()")
    evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    settle()
    check("!document.querySelector('.aside').classList.contains('visible')", 'Escape closes feed navigation')
    check("document.querySelector('.ig-monogram')!==null", 'image-less fallback present')
    check("!document.querySelector('[src^=\"https://\"]')", 'fixture loads no external images or feed content')
    command('Fetch.enable', {'patterns': [{'resourceType': 'Image', 'requestStage': 'Request'}]})
    evaluate("""
    window.imageFixture = (id, hero, width, images, html) => {
      const node=article(id), text=node.querySelector('.text'), meta=text.querySelector('.ig-entry-meta');
      meta.dataset.image=hero; meta.dataset.imageWidth=width; meta.dataset.images=JSON.stringify(images);
      text.replaceChildren(meta); text.insertAdjacentHTML('beforeend',html);
      document.querySelector('#stream').append(node); return node;
    };
    const echo='https://i2-prod.liverpoolecho.co.uk/';
    imageFixture(26, echo+'incoming/article123.ece/ALTERNATES/s98/0_Test.jpg', 98,
      [{url:echo+'incoming/article123.ece/ALTERNATES/s615/0_Test.jpg',width:615},
       {url:echo+'article999.ece/ALTERNATES/s2400/0_Other.jpg',width:2400}],
      '<img src="'+echo+'assets/logo.svg"><img class="fixture-hero" data-original="'+echo+'article123.ece/ALTERNATES/s615/0_Test.jpg" srcset="'+echo+'article123.ece/ALTERNATES/s508/0_Test.jpg 508w, '+echo+'article123.ece/ALTERNATES/s1200f/0_Test.jpg 1200w">');
    """)
    settle()
    check("document.querySelector('#flux_26 .ig-media img').src.includes('/article123.ece/ALTERNATES/s1200f/')", 'Echo card selects 1200px version across incoming/crop aliases, skipping logos and unrelated images')
    evaluate("document.querySelector('#flux_26 .ig-card').click()")
    settle()
    check("document.querySelector('dialog .fixture-hero').src.includes('/s1200f/') && getComputedStyle(document.querySelector('dialog .fixture-hero')).filter==='brightness(0.8) saturate(0.95)'", 'reader upgrades matching Echo image and retains dimming')
    evaluate("document.querySelector('dialog').close()")
    settle()
    evaluate("""
    const globe='https://www.wirralglobe.co.uk/resources/images/';
    imageFixture(27, globe+'4000/?type=app&htype=0', 360, [{url:globe+'4000/'}],
      '<img src="'+globe+'9999?type=thumb"><img class="fixture-hero" srcset="'+globe+'4000.jpg?type=mds-article-575 575w, '+globe+'4000.jpg?type=mds-article-962 962w">');
    imageFixture(28, globe+'5000/?type=app', 360, [],
      '<img class="fixture-hero" srcset="'+globe+'5000/?type=mds-article-962 962w, '+globe+'5000/?type=mds-article-620 1401w">');
    """)
    settle()
    check("document.querySelector('#flux_27 .ig-media img').src==='https://www.wirralglobe.co.uk/resources/images/4000/'", 'Globe card prefers supplied original enclosure over app thumbnail and site logos')
    check("document.querySelector('#flux_28 .ig-media img').src.includes('type=mds-article-962')", 'Globe CDN dimensions override misleading larger srcset descriptors')
    evaluate("document.querySelector('#flux_27 .ig-card').click()")
    settle()
    check("document.querySelector('dialog .fixture-hero').src==='https://www.wirralglobe.co.uk/resources/images/4000/'", 'srcset-only Globe reader image upgrades to matching original')
    evaluate("document.querySelector('dialog').close()")
    settle()
    evaluate("""
    {
    const cdn='https://cdn.example.invalid/';
    imageFixture(29,cdn+'small.jpg',400,[],
      '<picture><source srcset="'+cdn+'medium.jpg 640w, '+cdn+'large.jpg 1600w"><img class="fixture-hero" data-original="'+cdn+'small.jpg" width="400" data-srcset="'+cdn+'small.jpg 1x, '+cdn+'retina.jpg 2x"></picture>');
    const echo='https://i2-prod.liverpoolecho.co.uk/';
    imageFixture(30,echo+'incoming/article777.ece/ALTERNATES/s98/0_Fail.jpg',98,
      [{url:echo+'incoming/article777.ece/ALTERNATES/s615/0_Fail.jpg',width:615}],
      '<img class="fixture-hero" data-original="'+echo+'article777.ece/ALTERNATES/s1200f/0_Fail.jpg">');
    imageFixture(31,echo+'article888.ece/ALTERNATES/s98/0_Only.jpg',98,
      [{url:echo+'article999.ece/ALTERNATES/s2400/0_Other.jpg',width:2400}],'<img src="'+cdn+'unrelated.jpg" width="2400">');
    imageFixture(32,'',0,[],'<p>No image</p>');
    }
    """)
    settle()
    check("document.querySelector('#flux_29 .ig-media img').src==='https://cdn.example.invalid/large.jpg'", 'generic picture, lazy srcset and density variants select highest supplied resolution')
    evaluate("document.querySelector('#flux_30 .ig-media img').loading='eager'")
    for _ in range(10):
        settle()
        if evaluate("document.querySelector('#flux_30 .ig-media img').src.includes('/s615/')"):
            break
    check("document.querySelector('#flux_30 .ig-media img').src.includes('/s615/')", 'failed high-resolution thumbnail falls back to working smaller version')
    check("document.querySelector('#flux_31 .ig-media img').src.includes('/article888.ece/ALTERNATES/s98/')", 'small lead image retained when larger images depict different assets')
    check("!document.querySelector('#flux_32 .ig-media img')", 'image-less monogram preserved')
    evaluate("document.querySelector('#flux_29 .ig-card').click()")
    settle()
    check("document.querySelector('dialog .fixture-hero').src==='https://cdn.example.invalid/large.jpg' && document.querySelector('dialog picture source').getAttribute('srcset')==='https://cdn.example.invalid/large.jpg'", 'picture sources cannot override the high-resolution reader selection')
    evaluate("document.querySelector('dialog').close()")
    settle()
    evaluate("document.querySelector('#flux_30 .ig-card').click()")
    settle()
    check("document.querySelector('dialog .fixture-hero').src.includes('/s615/')", 'reader image falls back when larger publisher variant fails')
    evaluate("document.querySelector('dialog').close()")
    settle()
    command('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/late'})
    for _ in range(100):
        if evaluate("document.querySelectorAll('.ig-card').length===24"):
            break
        time.sleep(.05)
    check("document.querySelectorAll('.ig-card').length===24", 'initialisation when asynchronous native core arrives late')
    if '--screenshots' in sys.argv:
        command('Fetch.disable')
        command('Network.enable')
        command('Network.setBlockedURLs', {'urls': ['https://*', 'http://example.invalid/*']})
        command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
        command('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/demo'})
        for _ in range(100):
            if evaluate("document.querySelectorAll('.ig-card').length===8"):
                break
            time.sleep(.05)
        check("document.querySelectorAll('.ig-card').length===8", 'editorial demo uses eight fictional stories')
        check("new Set([...document.querySelectorAll('.ig-media img')].map(img=>img.src)).size===8", 'each editorial card uses a different photo')
        evaluate("Promise.all([...document.images].map(img=>{img.loading='eager';return img.decode().catch(()=>{});})).then(()=>document.fonts.ready)")
        check("[...document.querySelectorAll('.ig-media img')].every(img=>img.complete && img.naturalWidth>=1280)", 'eight local licensed photos load at full demo resolution')
        for width, height, filename in [(1440,1000,'desktop-neutral.png'), (390,844,'mobile-grid-neutral.png'), (430,932,'mobile-grid-wide-neutral.png')]:
            command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width < 600})
            evaluate('window.scrollTo(0,0)')
            settle()
            screenshot(filename)
        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        evaluate("document.querySelector('#flux_1 .ig-card').click()")
        settle()
        check("document.querySelector('dialog[open]') && document.documentElement.scrollWidth<=innerWidth", 'editorial mobile reader opens without overflow')
        screenshot('mobile-reader-neutral.png')
    assert not errors, errors
    print('PASS no browser JavaScript exceptions', flush=True)
finally:
    if ws:
        ws.close()
    browser.terminate()
    server.shutdown()
