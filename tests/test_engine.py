import datetime as dt
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from src.engine import (
    normalize_title, doi_key, unique_id, iso_date_from_parts,
    crossref_publication_date, classify_type, rank_paper, relevant_to_catalog, merge_papers, fetch_crossref, fetch_pubmed,
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

    def test_explicit_news_type_lowers_priority_without_removing_record(self):
        base={'doi':'10.1/news','title':'Cancer research','abstract':'','tier':'cross','online_date':None}
        research=rank_paper({**base,'publication_types':['Journal Article']})
        news=rank_paper({**base,'publication_types':['News']})
        self.assertEqual(news['priority_score'],research['priority_score']-15)
        self.assertEqual(news['publication_types'],['News'])

    def test_cross_journal_requires_cancer_context(self):
        unrelated={'title':'The shifting sands of research independence: why mid-career scientists crave security',
                   'abstract':'', 'tier':'cross'}
        self.assertFalse(relevant_to_catalog(unrelated))
        self.assertTrue(relevant_to_catalog({**unrelated,'title':'New immunotherapy for glioblastoma'}))
        self.assertTrue(relevant_to_catalog({**unrelated,'tier':'core'}))

    def test_broad_specialist_requires_cancer_context_without_hiding_anesthesia(self):
        broad={'title':'New treatment for inflammatory bowel disease', 'abstract':'',
               'journal':'Gut','tier':'specialist','requires_oncology_context':True}
        self.assertFalse(relevant_to_catalog(broad))
        self.assertTrue(relevant_to_catalog({**broad,'title':'Colorectal cancer trial'}))
        self.assertTrue(relevant_to_catalog({**broad,'requires_oncology_context':False,
                                              'journal':'Anesthesiology'}))

    def test_broad_specialist_is_filtered_at_source(self):
        journals=[{'name':'Gut','issn':'0017-5749','tier':'specialist',
                   'requires_oncology_context':True}]
        response={'message':{'items':[
            {'DOI':'10.1/ibd','title':['Inflammatory bowel disease'], 'ISSN':['0017-5749']},
            {'DOI':'10.1/cancer','title':['Colorectal cancer trial'], 'ISSN':['0017-5749']},
        ]}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals)
        self.assertEqual([p['doi'] for p in out],['10.1/cancer'])

    def test_crossref_multidisciplinary_paper_is_filtered(self):
        journals=[{'name':'Nature','tier':'cross'}]
        response={'message':{'items':[
            {'DOI':'10.1/unrelated','title':['The shifting sands of research independence'], 'container-title':['Nature']},
            {'DOI':'10.1/cancer','title':['Tumor response to immunotherapy'], 'container-title':['Nature']},
        ]}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals)
        self.assertEqual([p['doi'] for p in out],['10.1/cancer'])

    def test_merge_prefers_abstract(self):
        a={'doi':'10.1/A','title':'T','abstract':'','source':'crossref'}
        b={'doi':'https://doi.org/10.1/a','title':'T','abstract':'Detailed abstract','pmid':'123','source':'pubmed'}
        r=merge_papers([a,b])
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['abstract'],'Detailed abstract')
        self.assertEqual(r[0]['pmid'],'123')

    def test_same_pmid_in_one_batch_merges_when_doi_is_missing_from_one(self):
        papers=[{'pmid':'123','title':'Study','abstract':'','source':'crossref'},
                {'pmid':'123','doi':'10.1/new','title':'Study','abstract':'Details','source':'pubmed'}]
        result=merge_papers(papers)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['doi'],'10.1/new')
        self.assertEqual(result[0]['abstract'],'Details')

    def test_conflicting_dois_for_same_pmid_are_not_silently_merged(self):
        papers=[{'pmid':'123','doi':'10.1/a'}, {'pmid':'123','doi':'10.1/b'}, {'pmid':'123'}]
        self.assertEqual(len(merge_papers(papers)),3)

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

    def test_crossref_journal_alias_accepted(self):
        journals=[{'name':'Anesthesia and analgesia','aliases':['Anesthesia & Analgesia'],'tier':'specialist'}]
        response={'message':{'items':[{'DOI':'10.1/alias','title':['A paper'],'container-title':['Anesthesia & Analgesia']}]}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals,now=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc))
        self.assertEqual(len(out),1)

    def test_crossref_issn_filter_and_exact_validation(self):
        journals=[{'name':'Paediatric anaesthesia','issn':'1155-5645','tier':'specialist'}]
        response={'message':{'items':[
            {'DOI':'10.1/yes','title':['A paper'],'container-title':['Pediatric Anesthesia'],'ISSN':['1155-5645']},
            {'DOI':'10.1/no','title':['Wrong serial'],'container-title':['Other'],'ISSN':['9999-9999']}
        ]}}
        with patch('src.engine.http_get_json',return_value=response) as fetch,patch('src.engine.time.sleep'):
            out=fetch_crossref(journals,now=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc))
        self.assertEqual([paper['doi'] for paper in out],['10.1/yes'])
        self.assertIn('issn:1155-5645',fetch.call_args.args[1]['filter'])

    def test_crossref_reindexed_old_paper_is_ignored(self):
        journals=[{'name':'Anesthesiology','issn':'0003-3022','tier':'specialist'}]
        response={'message':{'items':[
            {'DOI':'10.1/new','title':['New'],'container-title':['Anesthesiology'],'ISSN':['0003-3022'],'published-online':{'date-parts':[[2026,10,13]]}},
            {'DOI':'10.1/old','title':['Old reindexed'],'container-title':['Anesthesiology'],'ISSN':['0003-3022'],'published-online':{'date-parts':[[2020,1,1]]}}
        ]}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals,now=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc),max_publication_age_days=45)
        self.assertEqual([paper['doi'] for paper in out],['10.1/new'])

    def test_crossref_future_publication_date_is_not_alerted(self):
        journals=[{'name':'Cancer Cell','issn':'1535-6108','tier':'core'}]
        response={'message':{'items':[
            {'DOI':'10.1/future','title':['Future article'],'ISSN':['1535-6108'],
             'published-online':{'date-parts':[[2026,11,1]]}},
            {'DOI':'10.1/today','title':['Current article'],'ISSN':['1535-6108'],
             'published-online':{'date-parts':[[2026,10,30]]}}
        ]}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            out=fetch_crossref(journals,now=dt.datetime(2026,10,30,tzinfo=dt.timezone.utc))
        self.assertEqual([paper['doi'] for paper in out],['10.1/today'])

    def test_crossref_reads_all_pages_with_a_fixed_index_window(self):
        now=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc)
        journal={'name':'Cancer Cell','issn':'1535-6108','tier':'core'}
        def item(i):
            return {'DOI':f'10.1234/{i}','ISSN':['1535-6108'],
                    'title':[f'Paper {i}'],'published-online':{'date-parts':[[2026,10,14]]}}
        pages=[{'message':{'items':[item(i) for i in range(60)],'next-cursor':'next'}},
               {'message':{'items':[item(60)]}}]
        with patch('src.engine.http_get_json',side_effect=pages) as search,patch('src.engine.time.sleep'):
            papers=fetch_crossref([journal],now=now)
        self.assertEqual(len(papers),61)
        first=search.call_args_list[0].args[1]
        second=search.call_args_list[1].args[1]
        self.assertEqual(first['cursor'],'*')
        self.assertEqual(second['cursor'],'next')
        self.assertIn('until-index-date:2026-10-14T00:00:00',first['filter'])

    def test_crossref_accepts_exactly_full_final_page_without_cursor(self):
        journal={'name':'Cancer Cell','issn':'1535-6108','tier':'core'}
        with patch('src.engine.http_get_json',return_value={'message':{'items':[{}]*60}}),patch('src.engine.time.sleep'):
            self.assertEqual(fetch_crossref([journal]),[])

    def test_crossref_rejects_missing_cursor_before_reported_total(self):
        journal={'name':'Cancer Cell','issn':'1535-6108','tier':'core'}
        response={'message':{'items':[{}]*60,'total-results':61}}
        with patch('src.engine.http_get_json',return_value=response),patch('src.engine.time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'before its reported total'):
                fetch_crossref([journal])

    def test_pubmed_title_with_xml_text_is_parsed(self):
        xml = b'''<PubmedArticleSet><PubmedArticle>
          <MedlineCitation><PMID>123</PMID><Article>
            <Journal><Title>Journal of Clinical Oncology</Title></Journal>
            <ArticleTitle>Title <i>with</i> markup</ArticleTitle>
            <Abstract><AbstractText>Abstract text</AbstractText></Abstract>
            <PublicationTypeList><PublicationType>News</PublicationType></PublicationTypeList>
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
        self.assertEqual(out[0]['publication_types'], ['News'])

    def test_pubmed_nlm_id_handles_journal_title_variant(self):
        xml=b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>456</PMID>
        <MedlineJournalInfo><NlmUniqueID>9206575</NlmUniqueID></MedlineJournalInfo>
        <Article><Journal><Title>Pediatric Anesthesia</Title></Journal><ArticleTitle>Study</ArticleTitle></Article>
        </MedlineCitation></PubmedArticle></PubmedArticleSet>'''
        journals=[{'name':'Paediatric anaesthesia','issn':'1155-5645','nlm_id':'9206575','tier':'specialist'}]
        with patch('src.engine.http_get_json',return_value={'esearchresult':{'idlist':['456']}}) as fetch,patch('src.engine._request',return_value=xml),patch('src.engine.time.sleep'):
            out=fetch_pubmed(journals)
        self.assertEqual(out[0]['journal'],'Paediatric anaesthesia')
        self.assertIn('1155-5645',fetch.call_args.args[1]['term'])

    def test_pubmed_fetches_results_beyond_first_page(self):
        first = [str(i) for i in range(1, 501)]
        pages = [
            {'esearchresult': {'count': '501', 'idlist': first}},
            {'esearchresult': {'count': '501', 'idlist': ['501']}},
        ]
        xml = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>501</PMID>
        <Article><Journal><Title>Journal of Clinical Oncology</Title></Journal>
        <ArticleTitle>Later page paper</ArticleTitle></Article></MedlineCitation>
        </PubmedArticle></PubmedArticleSet>'''
        journals = [{'name': 'Journal of Clinical Oncology', 'tier': 'core'}]
        with patch('src.engine.http_get_json', side_effect=pages) as search, \
             patch('src.engine._request', side_effect=[b'<PubmedArticleSet/>', b'<PubmedArticleSet/>', xml]) as fetch, \
             patch('src.engine.time.sleep'):
            out = fetch_pubmed(journals)
        self.assertEqual(search.call_args_list[1].args[1]['retstart'], 500)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(out[0]['pmid'], '501')

    def test_pubmed_rejects_overlapping_pages_instead_of_silently_missing_results(self):
        pages = [
            {'esearchresult': {'count': '3', 'idlist': ['1', '2']}},
            {'esearchresult': {'count': '3', 'idlist': ['2']}},
        ]
        journals = [{'name': 'Journal of Clinical Oncology', 'tier': 'core'}]
        with patch('src.engine.http_get_json', side_effect=pages), patch('src.engine.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'overlapping results pages'):
                fetch_pubmed(journals)

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

