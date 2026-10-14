import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scan

class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'config').mkdir()
        (self.root/'data').mkdir()
        (self.root/'config'/'journals.json').write_text(json.dumps({'journals':[{'name':'Cancer Cell','tier':'core','enabled':True}]}))
        (self.root/'config'/'settings.json').write_text(json.dumps({'monitoring':{'pubmed_created_days':3,'pubmed_batch_size':12,'crossref_indexed_hours':72,'crossref_journals_per_run':1,'max_new_per_run':10},'ai':{'enabled':True,'model':'gemini-3.1-flash-lite','max_calls_per_day':1,'max_calls_per_scan':1},'notifications':{'enabled':True,'score_threshold':0,'max_messages_per_scan':2}}))
        self.original_root=scan.ROOT
        self.original_data=scan.DATA
        scan.ROOT=self.root
        scan.DATA=self.root/'data'

    def tearDown(self):
        scan.ROOT=self.original_root
        scan.DATA=self.original_data
        self.tmp.cleanup()

    def paper(self):
        return {'doi':'10.1234/test','title':'Cancer Cell paper','journal':'Cancer Cell','abstract':'tumor microenvironment','online_date':None,'tier':'core','priority_score':75,'source':'pubmed'}

    def test_new_paper_then_dedup_without_secrets(self):
        with patch.object(scan,'fetch_pubmed',return_value=[self.paper()]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{},clear=True):
            scan.run()
            first=json.loads((self.root/'data'/'state.json').read_text())
            scan.run()
            second=json.loads((self.root/'data'/'state.json').read_text())
        self.assertEqual(len(first['seen']),1)
        self.assertEqual(len(second['seen']),1)
        self.assertEqual(second['ai_calls_per_day'],{})
        self.assertEqual(len(json.loads((self.root/'data'/'feed.json').read_text())['papers']),1)

    def test_ai_requires_explicit_free_ack(self):
        with patch.object(scan,'fetch_pubmed',return_value=[self.paper()]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{'GEMINI_API_KEY':'fake'},clear=True),patch.object(scan,'screen_abstract') as model:
            scan.run()
        model.assert_not_called()

    def test_ai_daily_cap(self):
        with patch.object(scan,'fetch_pubmed',return_value=[self.paper()]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{'GEMINI_API_KEY':'fake','AI_FREE_TIER_ACK':'YES'},clear=True),patch.object(scan,'screen_abstract',return_value={'triage_recommendation':'read_later'}) as model:
            scan.run()
            scan.run()
        self.assertEqual(model.call_count,1)

    def test_serverchan_daily_attempt_limit(self):
        settings_file=self.root/'config'/'settings.json'
        opts=json.loads(settings_file.read_text())
        opts['notifications']['channel']='serverchan'
        opts['notifications']['serverchan_max_calls_per_day']=1
        settings_file.write_text(json.dumps(opts))
        with patch.object(scan,'fetch_pubmed',return_value=[self.paper()]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{'SERVERCHAN_SENDKEY':'fake'},clear=True),patch.object(scan,'send_notification',return_value=False) as push:
            scan.run()
            scan.run()
        self.assertEqual(push.call_count,1)

    def test_failure_retries_message_without_duplicate_accepted(self):
        with patch.object(scan,'fetch_pubmed',return_value=[self.paper()]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{'SERVERCHAN_SENDKEY':'fake'},clear=True),patch.object(scan,'send_notification',side_effect=[False,True]) as push:
            scan.run()
            scan.run()
            scan.run()
        self.assertEqual(push.call_count,2)
        self.assertEqual(len(json.loads((self.root/'data'/'state.json').read_text())['sent']),1)

if __name__=='__main__':
    unittest.main()
