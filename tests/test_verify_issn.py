import unittest

from scripts.verify_issn import choose_issn


class IssnVerificationTests(unittest.TestCase):
    def test_exact_title_and_ampersand_variant(self):
        journal={'name':'Journal of Hematology & Oncology'}
        items=[{'title':'Journal of Hematology and Oncology','ISSN':['1756-8722']},
               {'title':'Hematology Journal','ISSN':['1111-1111']}]
        self.assertEqual(choose_issn(journal,items),'1756-8722')

    def test_ambiguous_exact_matches_are_not_written(self):
        journal={'name':'Cancer Research'}
        items=[{'title':'Cancer Research','ISSN':['0008-5472']},
               {'title':'Cancer Research','ISSN':['9999-9999']}]
        self.assertIsNone(choose_issn(journal,items))


if __name__=='__main__':
    unittest.main()

