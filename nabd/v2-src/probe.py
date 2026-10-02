"""Unauthenticated public checks. Only public profiles and status counts are logged."""
import concurrent.futures,datetime,json,pathlib,re,urllib.request,urllib.error
ROOT=pathlib.Path('nabd');MEMBERS=json.loads((ROOT/'v2-src/members.json').read_text());NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def check(member):
    row={'handle':member['x'],'x':{},'facebook':{}}
    urls={'x':'https://api.fxtwitter.com/2/profile/'+member['x']+'/statuses?count=20&_nabd='+NOW,'facebook':member['facebook']}
    for platform,url in urls.items():
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; NabdPublicCheck/2.0)','Accept':'application/json' if platform=='x' else 'text/html'})
            with urllib.request.urlopen(req,timeout=18) as r:
                body=r.read(3000000);row[platform]['http_status']=r.status
                if platform=='x':
                    data=json.loads(body);results=data.get('results',[]);row[platform].update({'ok':data.get('code')==200 and isinstance(results,list),'post_count':len(results) if isinstance(results,list) else 0,'cors':r.headers.get('Access-Control-Allow-Origin')})
                else:
                    text=body.decode('utf-8','replace');login='login' in r.url or 'You must log in' in text or 'Log in to Facebook' in text
                    row[platform].update({'login_or_gate_detected':login,'verified_timeline_fetched':False})
        except urllib.error.HTTPError as e:row[platform]={'ok':False,'http_status':e.code}
        except Exception as e:row[platform]={'ok':False,'error_type':type(e).__name__}
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,MEMBERS))
report={'checked_at':NOW,'authentication_used':False,'x_account_count':len(MEMBERS),'facebook_source_count':len(MEMBERS),'third_platform_present':False,'sources':results}
(ROOT/'provider-check-v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
