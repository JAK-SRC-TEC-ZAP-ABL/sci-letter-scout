import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scan

class ScanTests(unittest.TestCase):
    def test_conflicting_dois_do_not_migrate_existing_pmid_or_sent_marker(self):
        old={'pmid':'123','doi':None}
        state={'seen':{'pmid:123':old},'sent':['pmid:123']}
        papers=[{'pmid':'123','doi':'10.1/a'}, {'pmid':'123','doi':'10.1/b'}]
        scan.reconcile_pmid_identifiers(papers,state)
        self.assertEqual(list(state['seen']),['pmid:123'])
        self.assertEqual(state['sent'],['pmid:123'])

    def test_pmid_record_gains_doi_without_duplicate_or_repeat_notification(self):
        old={'pmid':'123','doi':None,'title':'Study','abstract':'','journal':'Cancer Cell',
             'tier':'core','first_detected':'2026-10-29T12:00:00+00:00'}
        state={'seen':{'pmid:123':old},'sent':['pmid:123']}
        paper={**old,'doi':'10.1234/new','abstract':'Updated abstract'}
        scan.reconcile_pmid_identifiers([paper],state)
        self.assertEqual(list(state['seen']),['doi:10.1234/new'])
        self.assertEqual(state['sent'],['doi:10.1234/new'])
        enriched=scan.enrich_seen(state['seen']['doi:10.1234/new'],paper)
        self.assertEqual(enriched['first_detected'],old['first_detected'])
        self.assertEqual(enriched['abstract'],'Updated abstract')

    def test_missing_doi_is_recovered_from_existing_record_by_pmid(self):
        state={'seen':{'doi:10.1234/new':{'pmid':'123','doi':'10.1234/new'}},'sent':[]}
        paper={'pmid':'123','doi':None}
        scan.reconcile_pmid_identifiers([paper],state)
        self.assertEqual(scan.unique_id(paper),'doi:10.1234/new')

    def test_later_pubmed_metadata_enriches_existing_paper_without_duplicate_alert(self):
        first={**self.paper(),'abstract':'','source':'crossref'}
        later={**first,'abstract':'New detailed abstract','source':'pubmed','pmid':'123','publication_types':['News']}
        with patch.object(scan,'fetch_pubmed',side_effect=[[],[later]]),patch.object(scan,'fetch_crossref',side_effect=[[first],[]]),patch.dict(os.environ,{},clear=True):
            scan.run()
            initial=json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))
            scan.run()
            updated=json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))
        self.assertEqual(len(updated['seen']),1)
        record=next(iter(updated['seen'].values()))
        self.assertEqual(record['abstract'],'New detailed abstract')
        self.assertEqual(record['publication_types'],['News'])
        self.assertEqual(record['first_detected'],next(iter(initial['seen'].values()))['first_detected'])

    def test_public_feed_keeps_recent_papers_from_both_specialties(self):
        papers=[{'doi':f'10.1/o{i}', 'specialty':'oncology', 'first_detected':f'2026-10-29T{i:03d}'} for i in range(400)]
        papers += [{'doi':f'10.1/a{i}', 'specialty':'anesthesiology', 'first_detected':f'2026-10-28T{i:03d}'} for i in range(3)]
        feed=scan.select_public_papers(papers, 300)
        self.assertEqual(len(feed),300)
        self.assertEqual(sum(p['specialty']=='anesthesiology' for p in feed),3)
        self.assertIn('10.1/o399', {p['doi'] for p in feed})

    def test_public_feed_excludes_legacy_unrelated_cross_journal_paper(self):
        papers=[{'doi':'10.1/offtopic','title':'Research independence','abstract':'',
                 'tier':'cross','journal':'Nature','first_detected':'2026-10-29T12:00:00+00:00'},
                {'doi':'10.1/on-topic','title':'Cancer immunotherapy','abstract':'',
                 'tier':'cross','journal':'Nature','first_detected':'2026-10-29T12:00:01+00:00'}]
        self.assertEqual([p['doi'] for p in scan.select_public_papers(papers)],['10.1/on-topic'])

    def test_existing_broad_journal_record_is_removed_from_public_feed(self):
        catalogue=self.root/'config'/'journals.json'
        content=json.loads(catalogue.read_text())
        content['journals'].append({'name':'Gut','tier':'specialist','enabled':True,
                                    'requires_oncology_context':True})
        catalogue.write_text(json.dumps(content))
        unrelated={**self.paper(),'doi':'10.1234/ibd','title':'Inflammatory bowel disease',
                   'abstract':'','journal':'Gut','tier':'specialist',
                   'first_detected':scan.utcnow().isoformat()}
        state={'seen':{scan.unique_id(unrelated):unrelated},'sent':[]}
        (self.root/'data'/'state.json').write_text(json.dumps(state))
        with patch.object(scan,'fetch_pubmed',return_value=[]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{},clear=True):
            scan.run()
        feed=json.loads((self.root/'data'/'feed.json').read_text(encoding='utf-8'))
        self.assertEqual(feed['papers'],[])

    def test_public_feed_puts_new_publication_ahead_of_recently_indexed_backfill(self):
        today=scan.utcnow().date().isoformat()
        papers=[{'doi':'10.1/backfill','title':'Cancer treatment','journal':'Cancer Cell',
                 'tier':'core','specialty':'oncology','online_date':'2026-01-01',
                 'first_detected':today+'T12:00:00+00:00'},
                {'doi':'10.1/fresh','title':'Cancer treatment','journal':'Cancer Cell',
                 'tier':'core','specialty':'oncology','online_date':today,
                 'first_detected':today+'T11:00:00+00:00'}]
        self.assertEqual([p['doi'] for p in scan.select_public_papers(papers)],
                         ['10.1/fresh','10.1/backfill'])

    def test_future_dated_articles_are_excluded_from_existing_state_and_feed(self):
        from datetime import timedelta
        today=scan.utcnow().date()
        future={**self.paper(),'doi':'10.1234/future',
                'online_date':(today+timedelta(days=2)).isoformat(),
                'first_detected':scan.utcnow().isoformat()}
        state={'seen':{scan.unique_id(future):future},'sent':[scan.unique_id(future)]}
        (self.root/'data'/'state.json').write_text(json.dumps(state),encoding='utf-8')
        with patch.object(scan,'fetch_pubmed',return_value=[future]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{},clear=True):
            scan.run()
        updated=json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))
        feed=json.loads((self.root/'data'/'feed.json').read_text(encoding='utf-8'))
        self.assertEqual(updated['seen'],{})
        self.assertEqual(updated['sent'],[])
        self.assertEqual(feed['papers'],[])

    def test_crossref_skips_unverified_issn_and_reports_coverage_gap(self):
        (self.root/'config'/'journals.json').write_text(json.dumps({'journals':[
            {'name':'Cancer Cell','tier':'core','enabled':True,'issn':'1535-6108'},
            {'name':'Unknown Journal','tier':'oncology','enabled':True,'issn':None}
        ]}), encoding='utf-8')
        with patch.object(scan,'fetch_pubmed',return_value=[]),patch.object(scan,'fetch_crossref',return_value=[]) as crossref,patch.dict(os.environ,{},clear=True):
            scan.run()
        self.assertEqual([j['name'] for j in crossref.call_args.args[0]],['Cancer Cell'])
        feed=json.loads((self.root/'data'/'feed.json').read_text(encoding='utf-8'))
        self.assertEqual(feed['source_health']['crossref'],'partial:missing_issn:1')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'config').mkdir()
        (self.root/'data').mkdir()
        (self.root/'config'/'journals.json').write_text(json.dumps({'journals':[{'name':'Cancer Cell','tier':'core','enabled':True,'issn':'1535-6108'}]}))
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
            first=json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))
            scan.run()
            second=json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))
        self.assertEqual(len(first['seen']),1)
        self.assertEqual(len(second['seen']),1)
        self.assertEqual(second['ai_calls_per_day'],{})
        self.assertEqual(len(json.loads((self.root/'data'/'feed.json').read_text(encoding='utf-8'))['papers']),1)

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
        self.assertEqual(len(json.loads((self.root/'data'/'state.json').read_text(encoding='utf-8'))['sent']),1)

    def test_anesthesiology_is_scanned_and_tagged_without_wechat_push(self):
        catalogue=self.root/'config'/'journals.json'
        content=json.loads(catalogue.read_text())
        content['journals'].append({'name':'Anesthesiology','specialty':'anesthesiology','tier':'specialist','enabled':True})
        catalogue.write_text(json.dumps(content))
        anesthesia={**self.paper(),'doi':'10.1234/anesthesia','title':'Anesthesia paper','journal':'Anesthesiology'}
        with patch.object(scan,'fetch_pubmed',return_value=[anesthesia]),patch.object(scan,'fetch_crossref',return_value=[]),patch.dict(os.environ,{'SERVERCHAN_SENDKEY':'fake'},clear=True),patch.object(scan,'send_notification') as push:
            scan.run()
        feed=json.loads((self.root/'data'/'feed.json').read_text(encoding='utf-8'))
        self.assertIn('anesthesiology',feed['subjects'])
        self.assertEqual(feed['journal_counts']['anesthesiology'],1)
        self.assertEqual(feed['papers'][0]['specialty'],'anesthesiology')
        self.assertEqual(feed['ai_status'],'disabled')
        self.assertEqual(feed['harmony_push_status'],'not_configured')
        push.assert_not_called()

if __name__=='__main__':
    unittest.main()

