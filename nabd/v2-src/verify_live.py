"""Check the real public deployment without reading or sending any passwords."""
import datetime,hashlib,json,pathlib,time,urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path('nabd');URL='https://ammarabushahin.github.io/fagersta-khutbah/nabd/';expected=json.loads((ROOT/'build-v2.json').read_text())['files']
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':URL,'tests':[],'errors':[]}
def check(name,ok):
    report['tests'].append({'test':name,'pass':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok:raise AssertionError(name)
try:
    ready=False
    for attempt in range(36):
        try:
            matched=[]
            for name in ['index.html','wall.html']:
                req=urllib.request.Request(URL+name+'?_verify='+str(time.time_ns()),headers={'Cache-Control':'no-cache','User-Agent':'NabdDeploymentCheck/2.0'})
                with urllib.request.urlopen(req,timeout=12) as r:matched.append(hashlib.sha256(r.read()).hexdigest()==expected[name])
            if all(matched):ready=True;break
        except Exception:pass
        time.sleep(5)
    check('Public HTTPS pages match tested build',ready)
    with sync_playwright() as pw:
        b=pw.chromium.launch(args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1000},locale='ar');page=ctx.new_page();page.set_default_timeout(20000);page.on('pageerror',lambda e:report['errors'].append(str(e)))
        response=page.goto(URL,wait_until='domcontentloaded',timeout=45000);check('Public shell opens',response.status==200)
        page.frame_locator('#content').locator('#v2-auth').wait_for(timeout=45000);f=page.frames[1];f.wait_for_function('typeof NabdV2!=="undefined"&&typeof busy!=="undefined"&&!busy',timeout=100000)
        check('Ten X and ten Facebook sources loaded',f.evaluate('state.accounts.length===10&&state.extra.facebook.length===10'))
        check('Settings locked by default',f.evaluate('NabdV2.status().locked'))
        report['source_statuses']=f.evaluate('statuses');report['displayed_x_posts']=f.locator('.tweet').count();report['real_post_ids']=f.evaluate('selectedPosts().map(p=>p.id)')
        check('At least one real X source returns posts',f.evaluate('state.posts.some(p=>!p.pending)'))
        page.screenshot(path=str(ROOT/'live-v2-desktop.png'),animations='disabled')
        page.locator('#edit-settings').click();f.locator('#v2-login').wait_for();check('Live settings action asks for password',f.locator('#admin-password').count()==1)
        f.locator('#admin-password').fill('intentionally-incorrect-live-test');f.locator('#login-submit').click();f.locator('#login-error').filter(has_text='غير صحيحة').wait_for();check('Incorrect password rejected on live site',f.evaluate('NabdV2.status().locked'));f.locator('[data-action="close"]').first.click()
        f.evaluate("document.cookie='nabd.verification=1; Path=/fagersta-khutbah/nabd/';")
        page.locator('#start-screen').click();page.wait_for_timeout(200);check('Browser enters fullscreen',page.evaluate('!!document.fullscreenElement'));before=page.evaluate('performance.timeOrigin');old=f.evaluate('performance.timeOrigin');page.locator('#hard-refresh').click();page.wait_for_timeout(1200);f=page.frames[1];f.wait_for_function('typeof NabdV2!=="undefined"&&!busy',timeout=100000)
        check('Full inner page reload without reloading shell',page.evaluate('performance.timeOrigin')==before and f.evaluate('performance.timeOrigin')!=old)
        check('Fullscreen retained after forced reload',page.evaluate('!!document.fullscreenElement'))
        check('Readable Nabd test cookie removed',not page.evaluate("document.cookie.includes('nabd.verification')"))
        check('Noindex on both real pages',page.locator('meta[name="robots"]').get_attribute('content').startswith('noindex') and f.locator('meta[name="robots"]').get_attribute('content').startswith('noindex'))
        report['screen_state']=page.evaluate('NabdShell.stats()')
        page.screenshot(path=str(ROOT/'live-v2-screen.png'),animations='disabled')
        page.evaluate('NabdShell.stop()');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300);check('Mobile viewport has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth') and f.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(ROOT/'live-v2-mobile.png'),animations='disabled');check('No uncaught JS errors',not report['errors']);b.close()
    report['ok']=True
except Exception as e:report.update({'ok':False,'failure':str(e)})
finally:
    (ROOT/'verification-v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if not report.get('ok'):raise SystemExit(1)
