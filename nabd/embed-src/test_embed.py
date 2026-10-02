"""Offline integration tests; mock widget frames are not live X embeds or views."""
import functools
import hashlib
import http.server
import json
import pathlib
import re
import secrets
import shutil
import tempfile
import threading
import time
import sys
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'nabd').resolve()
SITE = pathlib.Path(tempfile.mkdtemp(prefix='nabd-embed-test-'))
PASSWORD = 'embed-ui-fixture-only-not-the-deployed-password'
for name in ['index.html','wall.html']: shutil.copy(ROOT/name, SITE/name)
wall = (SITE/'wall.html').read_text()
m = re.search(r'const V2AUTH=(\{[^;]+);', wall)
auth = json.loads(m.group(1)); auth['salt'] = secrets.token_hex(24)
auth['hash'] = hashlib.pbkdf2_hmac('sha256', PASSWORD.encode(), bytes.fromhex(auth['salt']), auth['iterations'], 32).hex()
wall = wall[:m.start(1)] + json.dumps(auth) + wall[m.end(1):]
(SITE/'wall.html').write_text(wall)
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1',0), functools.partial(QuietHandler,directory=str(SITE)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL = 'http://127.0.0.1:%d/' % server.server_port
SDK = """(()=>{
const callbacks=window.twttr?._e||[];window.__embedCalls=[];
window.twttr={ready:f=>f(),widgets:{createTweet:async(id,target,options)=>{
window.__embedCalls.push({id,options});
const wrap=document.createElement('div');wrap.className='twitter-tweet';
const frame=document.createElement('iframe');frame.title='Local widget fixture: not a real X post';
frame.style.cssText='width:100%;height:370px;border:0;display:block';
frame.srcdoc='<html dir="rtl"><body style="font:17px Arial;padding:20px;background:#f4f4f6"><strong>إطار اختبار محلي</strong><p>هذه بيانات اختبار فقط وليست تغريدة حقيقية.</p><p>التضمين لا يزيد عداد مشاهدات X.</p><small>'+id+'</small></body></html>';
wrap.append(frame);target.append(wrap);return frame;
}}};callbacks.forEach(f=>f());})();"""
report={'test_mode':'offline fixtures with a separate test-only password; no live view generation','tests':[],'errors':[]}
def check(name, condition):
    report['tests'].append({'test':name,'pass':bool(condition)});print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    if not condition: raise AssertionError(name)
def handler(block_sdk=False):
    def route(r):
        u=urlsplit(r.request.url)
        if u.hostname=='127.0.0.1': return r.continue_()
        if u.hostname=='api.fxtwitter.com':
            if '/profile/' in u.path:
                handle=u.path.split('/profile/')[1].split('/')[0]
                n=int(hashlib.sha256(handle.encode()).hexdigest()[:7],16)
                posts=[{'id':str(1900000000000000000+n*100+j),'author':{'screen_name':handle,'name':handle},'text':'اختبار محلي فقط '+str(j),'created_timestamp':int(time.time())-j*120,'likes':0} for j in range(12)]
                return r.fulfill(status=200,content_type='application/json',body=json.dumps({'code':200,'results':posts}))
            return r.fulfill(status=404,content_type='application/json',body='{"code":404}')
        if u.hostname=='platform.twitter.com' and u.path=='/widgets.js':
            return r.abort() if block_sdk else r.fulfill(status=200,content_type='text/javascript',body=SDK)
        return r.abort()
    return route
with sync_playwright() as pw:
    launch={'headless':True,'args':['--no-sandbox']}
    if shutil.which('chromium'): launch['executable_path']=shutil.which('chromium')
    browser=pw.chromium.launch(**launch)
    ctx=browser.new_context(viewport={'width':1440,'height':1100},locale='ar')
    ctx.route('**/*',handler())
    page=ctx.new_page(); page.set_default_timeout(10000)
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    try:
        page.goto(URL,wait_until='domcontentloaded')
        f=page.frame_locator('#content')
        f.locator('.x-embedded-card').first.wait_for(timeout=20000)
        doc=next(x for x in page.frames if '/wall.html' in x.url)
        doc.wait_for_function('!busy && NabdXEmbeds.stats().loaded>0')
        check('Ten registered X and Facebook sources preserved',doc.evaluate('state.accounts.length===10&&state.extra.facebook.length===10'))
        check('All X cards use official widget hosts',f.locator('.x-embedded-card').count()==10 and f.locator('.tweet-body').count()==0)
        check('Explicit statement about non-counting embedded views',f.locator('.x-embed-note').inner_text().find('لا يزيدان')>=0)
        check('Edit lock remains enabled',doc.evaluate('NabdV2.status().locked'))
        check('Only documented display options passed to SDK',doc.evaluate('__embedCalls.length>0&&__embedCalls.every(c=>c.options.dnt===true&&c.options.lang==="ar"&&Object.keys(c.options).sort().join(",")==="align,cards,conversation,dnt,lang,theme")'))
        check('Widget library loaded once per document',doc.locator('script#nabd-x-widgets').count()==1)
        f.locator('.hero-actions [data-action="accounts"]').click()
        f.locator('#admin-password').fill(PASSWORD);f.locator('#login-submit').click()
        f.locator('#accounts-list').wait_for();f.locator('[data-action="close"]').first.click()
        f.locator('#global-limit').fill('3');f.locator('#global-limit').dispatch_event('change')
        doc.wait_for_function('NabdXEmbeds.stats().loaded===3')
        doc.evaluate('window.fixtureFrame=document.querySelector(".x-widget-host iframe");window.fixtureCalls=__embedCalls.length;')
        f.locator('.tweet [data-action="post-larger"]').first.click()
        check('First click zooms the embedded card',f.locator('.tweet .sizeval').first.inner_text()=='110%')
        check('Zoom preserves the same widget iframe',doc.evaluate('fixtureFrame===document.querySelector(".x-widget-host iframe")&&__embedCalls.length===fixtureCalls'))
        doc.evaluate('render();render();render();')
        check('Ordinary re-renders do not recreate embeds',doc.evaluate('fixtureFrame===document.querySelector(".x-widget-host iframe")&&__embedCalls.length===fixtureCalls'))
        second=f.locator('.tweet').nth(1).get_attribute('data-id')
        f.locator('.tweet [data-action="pin"]').nth(1).click()
        check('Pinning reorders actual embedded cards',f.locator('.tweet').first.get_attribute('data-id')==second)
        f.locator('.tweet [data-action="bookmark"]').first.click()
        check('Bookmark button continues to work',doc.evaluate('Object.values(state.cards).some(c=>c.saved)'))
        doc.evaluate('setSetting("theme","dark")')
        doc.wait_for_function('NabdXEmbeds.stats().loaded===3 && __embedCalls.slice(-3).every(c=>c.options.theme==="dark")')
        check('Official dark theme is applied',doc.evaluate('__embedCalls.slice(-3).every(c=>c.options.theme==="dark")'))
        doc.evaluate('setSetting("showMedia",false)')
        doc.wait_for_function('NabdXEmbeds.stats().loaded===3 && __embedCalls.slice(-3).every(c=>c.options.cards==="hidden")')
        check('Official media visibility option is applied',doc.evaluate('__embedCalls.slice(-3).every(c=>c.options.cards==="hidden")'))
        # Pending manual URL embeds by ID without waiting for the discovery provider.
        doc.evaluate('''()=>{state.posts.unshift(cleanPost({id:'1909999999999999999',handle:'Sample',name:'Local test only',manual:true,pending:true}));save();render();}''')
        f.locator('[data-id="1909999999999999999"].tweet').scroll_into_view_if_needed()
        doc.wait_for_function('__embedCalls.some(c=>c.id==="1909999999999999999")')
        check('Pending manual links use official SDK directly',doc.evaluate('__embedCalls.some(c=>c.id==="1909999999999999999")'))
        check('No custom view counters in embedded cards',f.locator('.tweet-stats').count()==0)
        f.locator('[data-action="platform"][data-platform="facebook"]').click()
        check('Facebook directory remains available',f.locator('.fb-source').count()==10)
        f.locator('[data-action="platform"][data-platform="x"]').click()
        doc.evaluate('setSetting("auto",false);setSetting("theme","light");setSetting("showMedia",true)')
        page.locator('#start-screen').click();page.wait_for_function('!!document.fullscreenElement')
        outer=page.evaluate('performance.timeOrigin');inner=doc.evaluate('performance.timeOrigin')
        page.locator('#hard-refresh').click()
        page.wait_for_function('NabdShell.stats().reloads>=1')
        page.wait_for_timeout(1500)
        doc=next(x for x in page.frames if '/wall.html' in x.url)
        doc.wait_for_function('typeof NabdXEmbeds!=="undefined" && !busy && NabdXEmbeds.stats().loaded>0')
        check('Full refresh recreates inner document and embeds',doc.evaluate('performance.timeOrigin')!=inner and doc.evaluate('NabdXEmbeds.stats().loaded>0'))
        check('Outer fullscreen survives the refresh',page.evaluate('performance.timeOrigin')==outer and page.evaluate('!!document.fullscreenElement'))
        check('Settings and edit lease preserved',doc.evaluate('state.settings.limit===3&&!NabdV2.status().locked'))
        page.evaluate('NabdShell.stop()');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
        check('No mobile horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth') and doc.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(ROOT/'embed-local-mobile.png'),animations='disabled')
        check('Noindex preserved in both documents',page.locator('meta[name="robots"]').get_attribute('content').startswith('noindex') and f.locator('meta[name="robots"]').get_attribute('content').startswith('noindex'))
        blocked=browser.new_context(viewport={'width':1440,'height':1100})
        blocked.route('**/*',handler(True))
        bp=blocked.new_page();bp.on('pageerror',lambda e:report['errors'].append(str(e)))
        bp.goto(URL,wait_until='domcontentloaded');bf=bp.frame_locator('#content')
        bf.locator('.tweet[data-embed-status="error"]').first.wait_for(timeout=20000)
        check('Blocked SDK produces an explicit fallback',bf.locator('.tweet[data-embed-status="error"] .x-original').first.get_attribute('href').startswith('https://x.com/'))
        check('Fallback includes a manual retry button',bf.locator('.tweet[data-embed-status="error"] .x-retry').first.is_visible())
        blocked.close()
        check('No uncaught JavaScript exceptions',not report['errors'])
        report['ok']=True
    except Exception as error:
        report['ok']=False; report['failure']=str(error)
        try: page.screenshot(path=str(ROOT/'embed-local-failure.png'),animations='disabled')
        except Exception: pass
        raise
    finally:
        (ROOT/'embed-local-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        browser.close();server.shutdown();shutil.rmtree(SITE,ignore_errors=True)
