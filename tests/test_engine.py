import datetime as dt
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from src.engine import (
    normalize_title, doi_key, unique_id, iso_date_from_parts,
    crossref_publication_date, classify_type, rank_paper, merge_papers, fetch_crossref, fetch_pubmed,
)
from src.notify import render_message, send_pushplus, send_serverchan, resolve_provider


class MetadataTests(unittest.TestCase):
    def test_doi_dedup(self):
        self.assertEqual(doi_key('https://doi.org/10.1000/XYZ.'),'10.1000/xyz')
        self.assertEqual(unique_id({'doi':'DOI:10.1111/ABC'}), 'doi:10.1111/abc')

    def test_journal_title_normalization(self):
        self.assertEqual(normalize_title('Nature  Medicine'),normalize_title('Nature-Medicine'))

    def test_date_parsing(self):
        self.assertEqual(iso_date_from_parts([2026,10,14]),'2026-10-14')
        self.assertIsNone(iso_date_from_parts([2026,13,14]))
        self.assertEqual(crossref_publication_date({'published-online':{'date-parts':[[2026,10,10]]}}),'2026-10-10')

    def test_study_type_and_priority(self):
        p=rank_paper({'doi':'10.1/a', 'title':'Single-cell atlas', 'abstract':'Single-cell RNA sequencing of tumors', 'tier':'core','online_date':dt.date.today().isoformat()})
        self.assertIn('single_cell',p['research_types'])
        self.assertEqual(p['evidence_level'],'metadata_or_abstract_only')
        self.assertEqual(p['letter_eligibility'],'unverified')
        self.assertGreater(p['priority_score'],40)

    def test_no_claim_without_abstract(self):
        p=rank_paper({'doi':'10.1/a','title':'Tumor gene study','abstract':'', 'tier':'core','online_date':None})
        self.assertEqual(p['evidence_level'],'metadata_or_abstract_only')
        self.assertNotIn('ai',p)

    def test_merge_prefers_abstract(self):
        a={'doi':'10.1/A','title':'T','abstract':'','source':'crossref'}
        b={'doi':'https://doi.org/10.1/a','title':'T','abstract':'Detailed abstract','pmid':'123','source':'pubmed'}
        r=merge_papers([a,b])
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['abstract'],'Detailed abstract')
        self.assertEqual(r[0]['pmid'],'123')

    def test_crossref_wrong_journal_rejected(self):
        journals=[{'name':'Cancer Cell','tier':'core'}]
        response={'message':{'items':[
            {'DOI':'10.1/yes','title':['A paper'],'container-title':['Cancer Cell'],'published-online':{'date-parts':[[2026,10,13]]}},
            {'DOI':'10.1/no','title':['A paper'],'container-title':['Different Journal'],'published-online':{'date-parts':[[2026,10,13]]}},
        ]}}
        with patch('src.engine.http_get_json', return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals,now=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc))
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['doi'],'10.1/yes')

    def test_pubmed_title_with_xml_text_is_parsed(self):
        xml = b'''<PubmedArticleSet><PubmedArticle>
          <MedlineCitation><PMID>123</PMID><Article>
            <Journal><Title>Journal of Clinical Oncology</Title></Journal>
            <ArticleTitle>Title <i>with</i> markup</ArticleTitle>
            <Abstract><AbstractText>Abstract text</AbstractText></Abstract>
          </Article></MedlineCitation>
          <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/test</ArticleId></ArticleIdList></PubmedData>
        </PubmedArticle></PubmedArticleSet>'''
        def fake_request(url, payload=None, retries=2):
            if 'esearch.fcgi' in url:
                return b'{"esearchresult":{"idlist":["123"]}}'
            return xml
        journals=[{'name':'Journal of Clinical Oncology','tier':'core'}]
        with patch('src.engine._request', side_effect=fake_request), patch('src.engine.time.sleep'):
            out=fetch_pubmed(journals, days=3, batch_size=12)
        self.assertEqual(out[0]['title'], 'Title with markup')
        self.assertEqual(out[0]['doi'], '10.1/test')

    def test_html_escape_in_push(self):
        content=render_message([{'title':'<script>alert(1)</script>', 'journal':'Cancer Cell','doi':'10.1/test','priority_score':70,'ai':{'potential_letter_angle':'<b>method?</b>'}}])
        self.assertNotIn('<script>',content)
        self.assertIn('&lt;script&gt;',content)
        self.assertIn('待核查角度',content)

    def test_serverchan_requires_secret(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertFalse(send_serverchan([{'title':'X'}]))
            self.assertEqual(resolve_provider(), 'none')

    def test_auto_channel_prefers_serverchan(self):
        with patch.dict('os.environ',{'SERVERCHAN_SENDKEY':'fake','PUSHPLUS_TOKEN':'other'},clear=True):
            self.assertEqual(resolve_provider(),'serverchan')

    def test_no_push_without_secret(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertFalse(send_pushplus([{'title':'X'}]))


if __name__=='__main__':
    unittest.main()
