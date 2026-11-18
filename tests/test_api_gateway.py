import json, os, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from nixlms_api.keys import APIKeyStore
from nixlms_api.server import RateLimiter, create_server

class FakeAssistant:
    def start_runtime(self):
        return {"scheduler_started": False}
    def respond(self, message, use_language=True, record=True):
        return "Nix recebeu: " + message

class APIKeyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.store=APIKeyStore(Path(self.temp.name)/"keys.sqlite3")
    def tearDown(self): self.temp.cleanup()
    def test_create_authenticate_revoke(self):
        item=self.store.create("test-client",["chat:write"],ttl_days=1)
        self.assertTrue(item["token"].startswith("nix_"))
        identity=self.store.authenticate(item["token"])
        self.assertEqual(identity["label"],"test-client")
        self.assertEqual(identity["scopes"],["chat:write"])
        self.assertTrue(self.store.revoke(item["prefix"]))
        self.assertIsNone(self.store.authenticate(item["token"]))
    def test_reject_invalid_scopes(self):
        with self.assertRaises(ValueError): self.store.create("bad",["admin:*"])
    def test_listing_does_not_expose_secret(self):
        item=self.store.create("client")
        rows=self.store.list()
        self.assertNotIn("token",rows[0]); self.assertNotIn(item["token"],str(rows))

class RateLimiterTests(unittest.TestCase):
    def test_limit_is_per_identity(self):
        limiter=RateLimiter(limit=1,window=60)
        self.assertTrue(limiter.allow("a")); self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

class APIServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=APIKeyStore(Path(self.temp.name)/"keys.sqlite3")
        self.key=self.store.create("test",["chat:write","models:read"])["token"]
        self.server=create_server(host="127.0.0.1",port=0,assistant=FakeAssistant(),key_store=self.store)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_address[1]}"
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2); self.temp.cleanup()
    def request(self,path,body=None,key=None):
        data=json.dumps(body).encode() if body is not None else None
        headers={"Content-Type":"application/json"}
        if key: headers["Authorization"]="Bearer "+key
        req=urllib.request.Request(self.url+path,data=data,headers=headers)
        return urllib.request.urlopen(req,timeout=3)
    def test_health_and_chat(self):
        self.assertTrue(json.loads(self.request("/health").read())["ok"])
        result=json.loads(self.request("/v1/chat/completions",{"messages":[{"role":"user","content":"oi"}]},self.key).read())
        self.assertEqual(result["choices"][0]["message"]["content"],"Nix recebeu: oi")
    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as error: self.request("/v1/models")
        self.assertEqual(error.exception.code,401)
    def test_scopes_enforced(self):
        read_only=self.store.create("read-only",["models:read"])["token"]
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/v1/chat",{"message":"oi"},read_only)
        self.assertEqual(error.exception.code,403)
    def test_models_endpoint(self):
        result=json.loads(self.request("/v1/models",key=self.key).read())
        self.assertEqual(result["data"][0]["id"],"nixlms")

class RemoteBindTests(unittest.TestCase):
    def test_remote_bind_requires_opt_in(self):
        old=os.environ.pop("NIXLMS_API_ALLOW_REMOTE",None)
        temp=tempfile.TemporaryDirectory()
        try:
            with self.assertRaises(RuntimeError):
                create_server(host="0.0.0.0",port=8767,key_store=APIKeyStore(Path(temp.name)/"keys.db"))
        finally:
            if old is not None: os.environ["NIXLMS_API_ALLOW_REMOTE"]=old
            temp.cleanup()

if __name__=="__main__": unittest.main()
