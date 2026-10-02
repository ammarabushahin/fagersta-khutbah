"""One deployment smoke test against genuine public X embeds; no view assertions."""
import datetime
import hashlib
import json
import pathlib
import time
import urllib.request
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path('nabd')
URL = 'https://ammarabushahin.github.io/fagersta-khutbah/nabd/'
expected = json.loads((ROOT/'build-embed.json').read_text())['files']
report = {'url':URL,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'network':'real public deployment and official X widgets; not fixtures',
          'tests':[],'errors':[],'view_count_increase_claimed':False}
def check(name, ok):
    report['tests'].append({'test':name,'pass':bool(ok)})
    print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok: raise AssertionError(name)
try:
    ready=False
    for attempt in range(36):
        try:
            actual={}
            for name in ['index.html','wall.html']:
                req=urllib.request.Request(URL+name+'?release-check='+str(int(time.time())),headers={'Cache-Control':'no-cache','User-Agent':'NabdEmbedDeploymentCheck/1.0'})
                with urllib.request.urlopen(req,timeout=15) as r:
                    actual[name]=hashlib.sha256(r.read()).hexdigest()
            if actual==expected: ready=True;break
        except Exception as e: report['last_http_error']=type(e).__name__
        time.sleep(5)
    check('Public HTTPS serves the checksum-verified embedding release',ready)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--no-sandbox'])
        ctx=browser.new_context(viewport={'width':1440,'height':1100},locale='ar')
        page=ctx.new_page();page.set_default_timeout(15000)
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        sdk_responses=[]
        page.on('response',lambda r:sdk_responses.append(r.status) if r.url=='https://platform.twitter.com/widgets.js' else None)
        page.goto(URL+'?v=2.1',wait_until='domcontentloaded',timeout=45000)
        frame=page.frame_locator('#content');frame.locator('.x-embedded-card').first.wait_for(timeout=90000)
        doc=next(f for f in page.frames if '/nabd/wall.html' in f.url)
        doc.wait_for_function('typeof NabdXEmbeds!=="undefined"&&!busy',timeout=90000)
        # Stop further scheduled refreshes in this isolated browser only.
        doc.evaluate('state.settings.auto=false;v2Status();')
        check('Default X cards are official embed containers',frame.locator('.x-embedded-card').count()==10 and frame.locator('.tweet-body').count()==0)
        check('Existing account sources and settings gate preserved',doc.evaluate('state.accounts.length===10&&state.extra.facebook.length===10&&NabdV2.status().locked'))
        check('View count limitation visible',frame.locator('.x-embed-note').inner_text().find('لا يزيدان')>=0)
        frame.locator('.x-embedded-card').first.scroll_into_view_if_needed()
        doc.wait_for_function('NabdXEmbeds.stats().loaded>0',timeout=45000)
        report['embed_status']=doc.evaluate('NabdXEmbeds.stats()')
        report['sdk_http_statuses']=sdk_responses
        check('Official widgets.js loaded from X',200 in sdk_responses)
        urls=frame.locator('.x-widget-host iframe').evaluate_all('(nodes)=>nodes.map(n=>n.src)')
        check('Tweet frames use the official X embed origin',any(urlsplit(u).hostname in ['platform.twitter.com','platform.x.com'] for u in urls))
        report['official_frame_count']=len(urls)
        content=[]
        for f in page.frames:
            if urlsplit(f.url).hostname in ['platform.twitter.com','platform.x.com'] and '/embed/' in f.url:
                try:
                    f.wait_for_selector('article,[data-testid="tweet"],[data-testid="tweetText"]',timeout=10000)
                    content.append({'origin':urlsplit(f.url).hostname,'content_detected':True,'text_length':len(f.locator('body').inner_text())})
                except Exception:
                    content.append({'origin':urlsplit(f.url).hostname,'content_detected':False})
        report['content_checks']=content
        check('Genuine post content rendered inside at least one X iframe',any(c['content_detected'] for c in content))
        page.screenshot(path=str(ROOT/'embed-live-desktop.png'),animations='disabled')
        page.locator('#start-screen').click();page.wait_for_function('!!document.fullscreenElement')
        inner=doc.evaluate('performance.timeOrigin');outer=page.evaluate('performance.timeOrigin')
        page.locator('#hard-refresh').click()
        page.wait_for_function('NabdShell.stats().reloads>=1');page.wait_for_timeout(1500)
        doc=next(f for f in page.frames if '/nabd/wall.html' in f.url)
        doc.wait_for_function('typeof NabdXEmbeds!=="undefined"&&!busy',timeout=90000)
        doc.evaluate('state.settings.auto=false;v2Status();')
        frame.locator('.x-embedded-card').first.scroll_into_view_if_needed()
        doc.wait_for_function('NabdXEmbeds.stats().loaded>0',timeout=45000)
        check('Full inner refresh reconstructs official embeds',doc.evaluate('performance.timeOrigin')!=inner and doc.evaluate('NabdXEmbeds.stats().loaded>0'))
        check('Fullscreen and outer document survive refresh',page.evaluate('performance.timeOrigin')==outer and page.evaluate('!!document.fullscreenElement'))
        page.evaluate('NabdShell.stop()');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1000)
        check('Real embeds fit the mobile layout',page.evaluate('document.documentElement.scrollWidth<=innerWidth') and doc.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(ROOT/'embed-live-mobile.png'),animations='disabled')
        check('Noindex retained in both documents',page.locator('meta[name="robots"]').get_attribute('content').startswith('noindex') and frame.locator('meta[name="robots"]').get_attribute('content').startswith('noindex'))
        check('No uncaught JavaScript errors',not report['errors'])
        browser.close()
    report['ok']=True
except Exception as error:
    report['ok']=False;report['failure']=str(error)
finally:
    (ROOT/'embed-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if not report['ok']: raise SystemExit(1)
