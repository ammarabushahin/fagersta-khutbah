"""Validate the isolated public Nabd wall using real network data and browser clicks."""
import datetime
import hashlib
import json
import pathlib
import time
import urllib.request
from playwright.sync_api import sync_playwright

URL = 'https://ammarabushahin.github.io/fagersta-khutbah/nabd/'
EXPECTED = '7df9d57cd35206e2351ab0e2b36f3d7afa2bf88abcf6e47a84b22495e53d445e'
ROOT = pathlib.Path('nabd')
report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'url': URL, 'tests': [], 'errors': []}

def check(name, condition):
    report['tests'].append({'test': name, 'pass': bool(condition)})
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)
    if not condition:
        raise AssertionError(name)

try:
    ready = False
    for attempt in range(36):
        try:
            req = urllib.request.Request(URL + '?verify=' + str(int(time.time())), headers={'User-Agent': 'NabdDeploymentCheck/1.0', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=12) as response:
                report['http_status'] = response.status
                report['html_sha256'] = hashlib.sha256(response.read()).hexdigest()
                ready = response.status == 200 and report['html_sha256'] == EXPECTED
            if ready:
                break
        except Exception as error:
            report['last_http_error'] = str(error)
        time.sleep(5)
    check('Public HTTPS page serves the exact tested release', ready)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='ar')
        page = context.new_page()
        page.set_default_timeout(15000)
        page.on('pageerror', lambda error: report['errors'].append(str(error)))
        api_responses = []
        page.on('response', lambda r: api_responses.append({'url': r.url, 'status': r.status}) if 'api.fxtwitter.com/' in r.url else None)
        response = page.goto(URL, wait_until='domcontentloaded', timeout=45000)
        check('Public page opens in a real Chromium browser', response.status == 200)
        page.wait_for_function('typeof busy !== "undefined" && !busy && state.posts.length > 0', timeout=65000)
        report['initial_cards'] = page.locator('.tweet').count()
        report['initial_source_status'] = page.evaluate('statuses')
        report['fetched_posts'] = page.evaluate('state.posts.length')
        report['initial_post_ids'] = page.evaluate('selectedPosts().map(p=>p.id)')
        check('Default ten genuine posts displayed', report['initial_cards'] == 10)
        check('Initial account is SalmaRashwani', page.evaluate('state.accounts[0].handle === "SalmaRashwani"'))
        report['live_timeline_api_ok'] = page.evaluate('!!statuses.salmarashwani?.ok && !statuses.salmarashwani?.cached')
        page.wait_for_timeout(400)
        page.screenshot(path=str(ROOT / 'live-desktop.png'), animations='disabled')
        page.locator('#global-limit').fill('3')
        page.locator('#global-limit').dispatch_event('change')
        check('Global count control works on deployed page', page.locator('.tweet').count() == 3)
        zoom_id = page.locator('.tweet').first.get_attribute('data-id')
        page.locator('.tweet [data-action="post-larger"]').first.click()
        report['zoom_value'] = page.evaluate('(id)=>state.cards[id]?.scale', zoom_id)
        check('First click enlarges a card after editing a number', report['zoom_value'] == 1.1)
        second = page.locator('.tweet').nth(1).get_attribute('data-id')
        page.locator('.tweet [data-action="pin"]').nth(1).click()
        check('Pin reorders the real cards', page.locator('.tweet').first.get_attribute('data-id') == second)
        page.locator('.tweet [data-action="bookmark"]').first.click()
        page.locator('[data-action="timer"]').first.click()
        page.locator('#interval-setting').fill('15')
        page.locator('[data-action="save-timer"]').click()
        check('Refresh seconds editable', page.evaluate('state.settings.interval === 15'))
        page.locator('[data-action="pause"]').click()
        before = page.evaluate('remaining')
        page.wait_for_timeout(1200)
        check('Countdown can be paused', page.evaluate('remaining') == before)
        page.locator('[data-action="pause"]').click()
        page.wait_for_timeout(1200)
        check('Countdown resumes', page.evaluate('remaining') < before)
        page.locator('[data-action="pause"]').click()
        real_link = page.evaluate('postUrl(state.posts[state.posts.length-1])')
        real_id = page.evaluate('state.posts[state.posts.length-1].id')
        page.evaluate('(id)=>{state.posts=state.posts.filter(p=>p.id!==id);save();render();}', real_id)
        page.locator('.hero-actions [data-action="add"]').click()
        page.locator('#links-input').fill(real_link + '\n' + real_link)
        page.locator('#add-links-submit').click()
        page.wait_for_function('!document.querySelector("#add-links-submit").disabled', timeout=30000)
        report['manual_post_loaded'] = page.evaluate('(id)=>!!state.posts.find(p=>p.id===id && p.manual && !p.pending)', real_id)
        check('Manual real URL is stored once', page.evaluate('(id)=>state.posts.filter(p=>p.id===id && p.manual).length===1', real_id))
        page.locator('[data-action="close"]').first.click()
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function('typeof busy !== "undefined" && !busy && state.posts.length>0', timeout=65000)
        check('Settings survive reloading', page.evaluate('state.settings.limit===3 && state.settings.interval===15 && !state.settings.auto'))
        check('Bookmark survives reloading', page.evaluate('Object.values(state.cards).some(c=>c.saved)'))
        page.locator('.hero-actions [data-action="accounts"]').click()
        check('Account editing controls available', page.locator('[data-account-limit="SalmaRashwani"]').count() == 1 and page.locator('[data-action="edit-account"]').count() == 1)
        page.locator('[data-action="close"]').first.click()
        page.evaluate('setSetting("limit",10)')
        page.set_viewport_size({'width': 390, 'height': 844})
        check('Mobile layout has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(ROOT / 'live-mobile.png'), full_page=True, animations='disabled')
        page.set_viewport_size({'width': 1440, 'height': 1050})
        page.evaluate('share()')
        share_url = page.locator('#share-url').input_value()
        viewer = context.new_page()
        viewer.on('pageerror', lambda error: report['errors'].append(str(error)))
        viewer.goto(share_url, wait_until='domcontentloaded', timeout=45000)
        viewer.wait_for_function('typeof busy !== "undefined" && !busy && state.posts.length>0', timeout=65000)
        check('Share URL opens presentation mode', viewer.evaluate('isScreen && sharedMode && document.body.classList.contains("presentation")'))
        check('Shared view does not expose saved bookmarks', viewer.evaluate('!Object.values(state.cards).some(c=>c.saved)'))
        viewer.screenshot(path=str(ROOT / 'live-screen.png'), animations='disabled')
        report['api_responses'] = api_responses
        check('No uncaught JavaScript exceptions', not report['errors'])
        browser.close()
    report['ok'] = True
except Exception as error:
    report['ok'] = False
    report['failure'] = str(error)
finally:
    (ROOT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
if not report['ok']:
    raise SystemExit(1)
