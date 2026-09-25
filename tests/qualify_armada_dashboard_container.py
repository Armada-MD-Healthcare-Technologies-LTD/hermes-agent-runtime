"""Run INSIDE the isolated qualification container; uses its synthetic key only."""
import json
import os
import time
import urllib.error
import urllib.request

base = 'http://127.0.0.1:8642'
for attempt in range(30):
    try:
        urllib.request.urlopen(base+'/health',timeout=2).close()
        break
    except OSError:
        if attempt == 29: raise
        time.sleep(1)
checks = []
for path, auth, method, expected in [
    ('/armada-dashboard/api/status',False,'GET',401),
    ('/armada-dashboard/api/status',True,'GET',200),
    ('/armada-dashboard/api/skills',True,'GET',200),
    ('/armada-dashboard/api/config',True,'GET',404),
    ('/armada-dashboard/api/status',True,'POST',405),
]:
    headers = {'Authorization':'Bearer '+os.environ['API_SERVER_KEY']} if auth else {}
    req = urllib.request.Request(base+path,headers=headers,method=method)
    try: response = urllib.request.urlopen(req,timeout=8)
    except urllib.error.HTTPError as error: response = error
    assert response.status == expected, (path,response.status,expected)
    payload = json.load(response)
    if expected == 200 and path.endswith('/status'):
        assert payload['source'] == 'live_private_hermes_dashboard'
        assert payload['managementEnabled'] is False
    if expected == 200 and path.endswith('/skills'):
        assert isinstance(payload,list) and payload
        assert all(set(item)=={'name','enabled','provenance'} for item in payload)
    checks.append({'path':path,'authenticated':auth,'method':method,'status':response.status})
print(json.dumps({'real_discovery':True,'passed':True,'checks':checks}))
