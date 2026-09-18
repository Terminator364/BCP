import tempfile, unittest, importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("bcp_server",HERE/"bcp_server.py")
bcp=importlib.util.module_from_spec(spec); spec.loader.exec_module(bcp)

class T(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        bcp.STATE_DIR=Path(self.tmp.name); bcp.DB_PATH=bcp.STATE_DIR/"bcp.sqlite3"; bcp.TOKEN_PATH=bcp.STATE_DIR/"bcp_token.txt"
        bcp.ensure_state()
    def tearDown(self): self.tmp.cleanup()
    def test_idempotent(self):
        p={"status":"ACTIVE","last_completed_action":"A","next_action":"B"}
        a=bcp.commit_event("demo","checkpoint",p,"same")
        z=bcp.commit_event("demo","checkpoint",p,"same")
        self.assertEqual("COMMITTED",a["result"]); self.assertEqual("ALREADY_COMMITTED",z["result"])
        self.assertEqual(a["event_hash"],z["event_hash"]); self.assertEqual(1,bcp.get_head("demo")["revision"])
    def test_resume_chain(self):
        a=bcp.commit_event("demo","checkpoint",{"last_completed_action":"one","next_action":"two"},"k1")
        bcp.commit_event("demo","checkpoint",{"last_completed_action":"two","next_action":"three"},"k2")
        ev=bcp.recent_events("demo"); self.assertEqual("GENESIS",ev[0]["prev_hash"])
        self.assertEqual(a["event_hash"],ev[1]["prev_hash"])
        self.assertEqual("three",bcp.get_head("demo")["next_action"])

if __name__=="__main__": unittest.main()
