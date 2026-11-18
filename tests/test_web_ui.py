import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class WebInterfaceTests(unittest.TestCase):
    def test_static_assets_exist(self):
        base=ROOT/"nixlms_web"/"static"
        for name in ("index.html","style.css","app.js"):
            self.assertTrue((base/name).is_file())
    def test_server_binds_loopback(self):
        source=(ROOT/"nixlms_web"/"server.py").read_text(encoding="utf-8")
        self.assertIn('host,port="127.0.0.1",8765',source)
        self.assertNotIn('host,port="0.0.0.0"',source)
    def test_upload_is_allowlisted(self):
        source=(ROOT/"nixlms_web"/"server.py").read_text(encoding="utf-8")
        self.assertIn('".txt"',source)
        self.assertNotIn('subprocess',source)
if __name__=="__main__": unittest.main()
