import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('armada_dashboard_projection', ROOT/'plugins/armada-dashboard/__init__.py')
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


class Adapter:
    def _check_auth(self, request):
        if request.headers.get('Authorization') != 'Bearer synthetic-gateway-token':
            return web.json_response({'error': 'unauthorized'}, status=401)
        return None


class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seen = []
        self.status, self.payload = 200, {'version': '0.21.5', 'secret': 'must-not-leak'}
        async def upstream(request):
            self.seen.append((request.method, request.path, request.headers.get('Authorization')))
            return web.json_response(self.payload, status=self.status)
        app = web.Application()
        app.router.add_route('*', '/{tail:.*}', upstream)
        self.upstream = TestServer(app)
        await self.upstream.start_server()
        self.env = patch.dict(os.environ, {'HERMES_DASHBOARD_SESSION_TOKEN': 't'*40})
        self.env.start()
        self.base = patch.object(projection, 'UPSTREAM', str(self.upstream.make_url('')).rstrip('/'))
        self.base.start()
        gateway = web.Application()
        projection.wire(gateway, Adapter())
        self.client = TestClient(TestServer(gateway))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.upstream.close()
        self.base.stop()
        self.env.stop()

    async def request(self, path='/api/status', method='GET', auth=True):
        return await self.client.request(method, '/armada-dashboard'+path,
            headers={'Authorization': 'Bearer synthetic-gateway-token'} if auth else {})

    async def test_auth_required_before_upstream(self):
        r = await self.request(auth=False)
        self.assertEqual(r.status,401); self.assertEqual(self.seen,[])

    async def test_status_is_live_and_allowlisted(self):
        r = await self.request(); result = await r.json()
        self.assertEqual(r.status,200); self.assertNotIn('secret',result)
        self.assertFalse(result['managementEnabled']); self.assertFalse(result['authorizesExecution'])
        self.assertEqual(result['version'],'0.21.5')
        self.assertEqual(self.seen,[('GET','/api/status','Bearer '+'t'*40)])
        self.assertEqual(r.headers['Cache-Control'],'no-store')

    async def test_skills_omit_contents_paths_and_secrets(self):
        self.payload=[{'name':'systematic-debugging','enabled':True,'provenance':'bundled',
                       'content':'private','path':'/home/private','api_key':'private'}]
        r=await self.request('/api/skills'); self.assertEqual(r.status,200)
        self.assertEqual(await r.json(),[{'name':'systematic-debugging','enabled':True,'provenance':'bundled'}])

    async def test_mutations_never_reach_dashboard(self):
        for method in ('POST','PUT','PATCH','DELETE'):
            r=await self.request('/api/status',method); self.assertEqual(r.status,405)
        self.assertEqual(self.seen,[])

    async def test_sensitive_paths_never_reach_dashboard(self):
        for path in ('/api/config','/api/config/raw','/api/env','/api/files','/api/conductor/missions','/'):
            r=await self.request(path); self.assertEqual(r.status,404)
        self.assertEqual(self.seen,[])

    async def test_arbitrary_profile_is_rejected(self):
        r=await self.request('/api/skills?profile=another');self.assertEqual(r.status,400)
        self.assertEqual(self.seen,[])

    async def test_missing_internal_auth_fails_closed(self):
        with patch.dict(os.environ,{'HERMES_DASHBOARD_SESSION_TOKEN':''}):
            r=await self.request();self.assertEqual(r.status,503)
        self.assertEqual(self.seen,[])

    async def test_upstream_errors_are_redacted(self):
        self.status=401;self.payload={'secret':'must-not-leak'}
        r=await self.request();self.assertEqual(r.status,503)
        self.assertNotIn('must-not-leak',await r.text())

    async def test_malformed_status_is_not_ready(self):
        self.payload={'ok':True}
        r=await self.request();self.assertEqual(r.status,503)

    async def test_oversized_response_is_rejected(self):
        self.payload={'version':'0.21.5','data':'a'*(projection.MAX_BYTES+1)}
        r=await self.request();self.assertEqual(r.status,503)

    async def test_malformed_skill_never_leaks_value(self):
        self.payload=[{'name':'secret\nvalue'}]
        r=await self.request('/api/skills');self.assertEqual(r.status,503)

    def test_registration_uses_existing_gateway(self):
        calls=[]
        class Context:
            def register_platform_handler(self,platform,handler):calls.append((platform,handler))
        projection.register(Context());self.assertEqual(calls,[('api_server',projection.wire)])

if __name__=='__main__':unittest.main()
