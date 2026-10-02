"""Build Nabd 2 from the verified, immutable Nabd 1 release. No private source files."""
import base64,hashlib,json,lzma,pathlib,sys
root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'nabd')
src=root/'v2-src'
if not src.exists():src=pathlib.Path(__file__).parent
parts=[root/'release'/f'part{i}.b64' for i in range(1,6)]
if all(p.exists() for p in parts):
    base=lzma.decompress(base64.b64decode(''.join(p.read_text().strip() for p in parts)),memlimit=268435456)
    if hashlib.sha256(base).hexdigest()!='d0f14cc571f012c60b145dfe70a48b13c2dc83956be2008d9c0bb966cf740c7b':raise ValueError('Original release integrity failed')
    base=base.replace(b'feed.appendChild(el);',b'const anchor=feed.children[ar.indexOf(p)];if(anchor!==el)feed.insertBefore(el,anchor||null);')
else:base=(src.parent/'base.html').read_bytes()
if hashlib.sha256(base).hexdigest()!='7df9d57cd35206e2351ab0e2b36f3d7afa2bf88abcf6e47a84b22495e53d445e':raise ValueError('Verified base hash mismatch')
html=base.decode('utf-8')
def once(old,new):
    global html
    if html.count(old)!=1:raise ValueError('Patch marker mismatch: '+old[:60])
    html=html.replace(old,new,1)
members=json.loads((src/'members.json').read_text())
assert len(members)==10 and all(set(m)=={'name','x','facebook'} for m in members)
auth=json.loads((src/'auth.json').read_text())
assert set(auth)=={'algorithm','iterations','salt','hash'} and auth['iterations']>=600000
extra={'schema':2,'balanced':True,'freshOnly':True,'facebook':[{'id':m['x'],'name':m['name'],'url':m['facebook'],'limit':10,'enabled':True} for m in members],'fbPosts':[]}
accounts=[{'handle':m['x'],'name':m['name'],'limit':10,'enabled':True} for m in members]
once('const palettes=',"defaults.accounts="+json.dumps(accounts,ensure_ascii=False)+";\ndefaults.extra="+json.dumps(extra,ensure_ascii=False)+";\ndefaults.settings.screenTitle='نبض المتابعة';\nconst palettes=")
once("s.lastSuccess=raw.lastSuccess;return s;}","s.lastSuccess=raw.lastSuccess;s.extra=tidyExtra(raw.extra);if(!raw.extra?.schema){for(const a of defaults.accounts)if(!s.accounts.some(b=>b.handle.toLowerCase()===a.handle.toLowerCase()))s.accounts.push({...a});s.accounts=s.accounts.slice(0,20);}return s;}")
once('settings:cfg.settings,cards:cfg.cards};','settings:cfg.settings,cards:cfg.cards,extra:cfg.extra};')
once("if(e.key.toLowerCase()==='r')refresh();","if(e.key.toLowerCase()==='r')hardRefresh();")
once("if(state.settings.auto&&!busy&&(!document.hidden||isScreen)&&navigator.onLine){remaining--;if(remaining<=0){remaining=state.settings.interval;refresh();}}","v2Tick();")
# Public-provider request URLs are unique; credentials are always omitted by getJSON.
once('const r=await fetch(url,{',"const requestURL=new URL(url,location.href);requestURL.searchParams.set('_nabd',Date.now().toString(36));const r=await fetch(requestURL.href,{")
extension=(src/'upgrade.js').read_text().replace('__AUTH__',json.dumps(auth))
once("render();if(!isScreen&&!sharedMode)save();refresh();",extension+"\nrender();if(!isScreen&&!sharedMode)save();refresh();")
once("if(sharedMode&&state.posts.some(p=>p.pending&&p.manual))","if(state.posts.some(p=>p.pending&&(p.manual||state.cards[p.id]?.saved||state.cards[p.id]?.pinned)))")
once("state.posts.filter(p=>p.pending&&p.manual).slice(0,50)","state.posts.filter(p=>p.pending&&(p.manual||state.cards[p.id]?.saved||state.cards[p.id]?.pinned)).slice(0,50)")
once('mergePosts([await fetchPost(t)]);renderFeed();',"const hydrated=await fetchPost(t);hydrated.manual=t.manual;mergePosts([hydrated]);renderFeed();")
meta='<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex"><meta name="googlebot" content="noindex,nofollow,nosnippet,noimageindex"><meta name="bingbot" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">'
once('</head>','<style>'+ (src/'upgrade.css').read_text()+'</style>'+meta+'</head>')
html=html.replace('كل ما يهمّك من X، في مساحة تُشبهك.','حساباتك العامة في مكان واحد، مع تحديث كامل وحالة مصادر واضحة.')
html=html.replace('مساحة تغريداتك الخاصة','متابعة عامة · تحكم محلي')
html=html.replace('تمت إضافة حساب SalmaRashwani.','تم تسجيل حسابات الفريق العامة.')
html=html.replace("'\\ufeff'+rows.map",'rows.map')
root.mkdir(parents=True,exist_ok=True)
(root/'wall.html').write_text(html,encoding='utf-8')
(root/'index.html').write_text((src/'shell.html').read_text(),encoding='utf-8')
report={'version':'2.0.0','files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['index.html','wall.html']},'x_accounts':len(accounts),'facebook_sources':len(extra['facebook']),'credentials_included':False,'security':'browser-local edit lock, not server auth'}
(root/'build-v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
