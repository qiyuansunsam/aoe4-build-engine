import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from app import ApiError, Crafter, make_handler, read_proxy_config


class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/redirect/models':
            self.send_response(302);self.send_header('Location','http://example.com/');self.end_headers();return
        data={'data':[{'id':'gpt-6-luna'}]}
        raw=json.dumps(data).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.last=body
        assert 'tools' not in body
        assert body['stream'] is False
        raw=json.dumps({'choices':[{'message':{'content':'Proposed opening. Verify timing before applying.'}}]}).encode()
        self.send_response(200);self.end_headers();self.wfile.write(raw)


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        (cls.root/'data').mkdir();(cls.root/'site/dist').mkdir(parents=True)
        (cls.root/'site/dist/index.html').write_text('<h1>test workspace</h1>',encoding='utf-8')
        (cls.root/'private.txt').write_text('private',encoding='utf-8')
        catalog={'provenance':{'steamBuildId':'fixture'},'coverage':{'warnings':['fixture only']},
                 'units':[{'id':'knight','name':'Royal Knight','civilization':'french','hp':190,'cost':{'food':140}}],
                 'buildings':[],'technologies':[]}
        for name,value in [('game-catalog',catalog),('build-library',{'builds':[]}),('game-library',{'games':[]})]:
            (cls.root/f'data/{name}.json').write_text(json.dumps(value),encoding='utf-8')
        cls.upstream=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        cls.thread=threading.Thread(target=cls.upstream.serve_forever,daemon=True);cls.thread.start()
        cls.env={'AOE_PROXY_BASE_URL':f'http://127.0.0.1:{cls.upstream.server_port}/v1',
                 'AOE_PROXY_API_KEY':'test-client-key','AOE_PROXY_CONFIG':str(cls.root/'absent.yaml')}
        cls.crafter=Crafter(cls.env,cls.root)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(cls.crafter,cls.root))
        cls.thread2=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread2.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.upstream.shutdown();cls.upstream.server_close();cls.temp.cleanup()
    def request(self,path='/',payload=None,headers=None):
        h=dict(headers or {})
        if payload is not None:h.setdefault('Content-Type','application/json')
        req=Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=h)
        try:
            with urlopen(req,timeout=5) as r:return r.status,r.read()
        except HTTPError as e:return e.code,e.read()
    def test_status_does_not_generate(self):
        status=self.crafter.status(refresh=True)
        self.assertTrue(status['reachable']);self.assertEqual(status['model'],'gpt-6-luna')
        self.assertNotIn('key',json.dumps(status))
    def test_generation_is_bounded_plain_text(self):
        result=self.crafter.generate({'prompt':'French knight opening','civilization':'french','mode':'rm_4v4'})
        self.assertEqual(result['draft']['status'],'unvalidated')
        self.assertIn('Verify timing',result['draft']['text'])
        payload=self.upstream.last
        self.assertLessEqual(payload['max_tokens'],2400);self.assertNotIn('tools',payload)
        content=json.loads(payload['messages'][1]['content'])
        self.assertEqual(content['installedEvidence']['selectedBaseRecords'][0]['hp'],190)
    def test_invalid_fields_and_prompt(self):
        for body in [{'prompt':'ab'},{'prompt':'x'*6001},{'prompt':'safe task','command':'del *'},{'prompt':'safe task','context':{}}]:
            with self.assertRaises(ApiError):self.crafter.generate(body)
    def test_rejects_external_proxy(self):
        with self.assertRaises(ApiError):Crafter({**self.env,'AOE_PROXY_BASE_URL':'https://example.com/v1'})
    def test_redirect_does_not_leave_loopback(self):
        crafter=Crafter({**self.env,'AOE_PROXY_BASE_URL':f'http://127.0.0.1:{self.upstream.server_port}/redirect'},self.root)
        with self.assertRaises(ApiError):crafter.request('/models')
    def test_missing_configuration(self):
        app=Crafter({'AOE_PROXY_CONFIG':str(self.root/'absent.yaml')},self.root)
        self.assertFalse(app.status()['configured'])
        with self.assertRaises(ApiError):app.generate({'prompt':'French opening'})
    def test_host_and_origin(self):
        self.assertEqual(self.request(headers={'Host':'attacker.invalid'})[0],403)
        self.assertEqual(self.request('/api/ai/generate',{'prompt':'French opening'},{'Origin':'https://attacker.invalid'})[0],403)
    def test_static_confined_and_games(self):
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/%2e%2e/%2e%2e/private.txt')[0],404)
        self.assertEqual(self.request('/api/games')[0],200)
    def test_api_generation_and_size(self):
        status,raw=self.request('/api/ai/generate',{'prompt':'French opening'})
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['draft']['status'],'unvalidated')
        self.assertEqual(self.request('/api/ai/generate',{'prompt':'x'*40000})[0],413)
    def test_client_config_parser(self):
        f=self.root/'test.yaml';f.write_text('host: "127.0.0.1"\nport: 8318\napi-keys:\n  - "fixture-client"\nauth-dir: ignored\n',encoding='utf-8')
        self.assertEqual(read_proxy_config(f),{'host':'127.0.0.1','port':'8318','key':'fixture-client'})
    def test_concurrency_guard(self):
        self.crafter.lock.acquire()
        try:
            with self.assertRaises(ApiError) as e:self.crafter.generate({'prompt':'French opening'})
            self.assertEqual(e.exception.status,429)
        finally:self.crafter.lock.release()


if __name__=='__main__':unittest.main()
