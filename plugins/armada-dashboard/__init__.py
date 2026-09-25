"""Read-only dashboard metadata on the existing authenticated API listener.
No configuration, secrets, session contents, files or execution API is exposed.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from aiohttp import ClientError, ClientSession, ClientTimeout, web

PREFIX = '/armada-dashboard'
UPSTREAM = 'http://127.0.0.1:9119'
MAX_BYTES = 262144
SAFE_NAME = re.compile(r'[A-Za-z0-9_./ -]{1,160}\Z')
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
           'X-Armada-Dashboard-Mode': 'metadata-read-only'}


def project_payload(path: str, payload: object) -> object:
    if path == '/api/status':
        if not isinstance(payload, dict) or not isinstance(payload.get('version'), str):
            raise ValueError('invalid_dashboard_status')
        version = payload['version']
        if not re.fullmatch(r'[A-Za-z0-9_.+\-]{1,80}', version):
            raise ValueError('invalid_dashboard_version')
        return {'version': version, 'source': 'live_private_hermes_dashboard',
                'mode': 'metadata-read-only', 'managementEnabled': False,
                'authorizesExecution': False}
    if path == '/api/skills':
        if not isinstance(payload, list) or len(payload) > 1000:
            raise ValueError('invalid_dashboard_skills')
        result = []
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get('name'), str):
                raise ValueError('invalid_dashboard_skill')
            if not SAFE_NAME.fullmatch(item['name']):
                raise ValueError('invalid_dashboard_skill_name')
            provenance = item.get('provenance')
            if provenance is not None and not isinstance(provenance, str):
                raise ValueError('invalid_dashboard_skill_provenance')
            result.append({'name': item['name'], 'enabled': item.get('enabled') is True,
                           'provenance': provenance if provenance in {'bundled', 'hub', 'agent'} else 'unknown'})
        return result
    raise ValueError('dashboard_projection_path_not_allowed')


def default_profile_request():
    from gateway.platforms.api_server import _api_request_profile
    from hermes_cli.profiles import get_active_profile_name
    return _api_request_profile.get() in (None, 'default') and get_active_profile_name() == 'default'


def wire(native, adapter):
    if not isinstance(native, web.Application) or not callable(getattr(adapter, '_check_auth', None)):
        raise ValueError('dashboard_gateway_auth_missing')
    async def lifecycle(app):
        session = ClientSession(timeout=ClientTimeout(total=5), trust_env=False)
        app[client_key] = session
        yield
        await session.close()
    client_key = web.AppKey('armada_dashboard_client', ClientSession)
    native.cleanup_ctx.append(lifecycle)
    async def handle(request):
        denial = adapter._check_auth(request)
        if denial is not None:
            return denial
        if not default_profile_request():
            return web.json_response({'error': 'dashboard_profile_not_supported'}, status=403, headers=HEADERS)
        if request.method != 'GET':
            return web.json_response({'error': 'dashboard_management_not_exposed'}, status=405, headers=HEADERS)
        path = '/' + request.match_info['tail']
        if path not in {'/api/status', '/api/skills'}:
            return web.json_response({'error': 'not_found'}, status=404, headers=HEADERS)
        if request.query_string:
            return web.json_response({'error': 'dashboard_scope_not_supported'}, status=400, headers=HEADERS)
        token = os.environ.get('HERMES_DASHBOARD_SESSION_TOKEN', '').strip()
        if len(token) < 32:
            return web.json_response({'error': 'dashboard_auth_not_configured'}, status=503, headers=HEADERS)
        try:
            async with request.app[client_key].get(UPSTREAM + path,
                    headers={'Authorization': 'Bearer ' + token}, allow_redirects=False) as response:
                if response.status != 200 or response.content_type != 'application/json':
                    raise ValueError('dashboard_upstream_unavailable')
                body = bytearray()
                async for chunk in response.content.iter_chunked(16384):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError('dashboard_response_too_large')
                payload = project_payload(path, json.loads(body))
            return web.json_response(payload, headers=HEADERS)
        except (ClientError, asyncio.TimeoutError, ValueError):
            return web.json_response({'error': 'dashboard_projection_unavailable'}, status=503, headers=HEADERS)
    native.router.add_route('*', PREFIX + '/{tail:.*}', handle)


def register(ctx):
    ctx.register_platform_handler('api_server', wire)
