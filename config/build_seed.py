import json
from pathlib import Path
TIER1 = '''Cancer Cell
Cancer Discovery
Nature Cancer
The Lancet Oncology
JAMA Oncology
Journal of Clinical Oncology
Annals of Oncology
Nature Medicine
Molecular Cancer
Cancer Research
Clinical Cancer Research
Cancer Communications
Journal of Hematology & Oncology
Journal for ImmunoTherapy of Cancer
Journal of Thoracic Oncology
JNCI: Journal of the National Cancer Institute
ESMO Open
Journal of Experimental & Clinical Cancer Research
Signal Transduction and Targeted Therapy
Nature Reviews Clinical Oncology'''.splitlines()
TIER2 = '''European Journal of Cancer
British Journal of Cancer
International Journal of Cancer
Molecular Oncology
Cancer Letters
Oncogene
Cancer Immunology Research
Cancer Epidemiology, Biomarkers & Prevention
npj Precision Oncology
JCO Precision Oncology
JNCI Cancer Spectrum
Journal of the National Comprehensive Cancer Network
Experimental Hematology & Oncology
Biomarker Research
Cancer Medicine
Journal of Cancer Research and Clinical Oncology
Cancer Immunology, Immunotherapy
Cancers
Translational Oncology
Clinical and Translational Medicine
OncoImmunology
Cancer Treatment Reviews
Frontiers in Oncology
Lung Cancer
Breast Cancer Research
Gynecologic Oncology
Annals of Surgical Oncology
Cancer Epidemiology
Cancer Prevention Research
Cancer Biology & Medicine'''.splitlines()
SPECIALIST = '''Gastroenterology
Gut
Clinical Gastroenterology and Hepatology
Journal of Hepatology
Hepatology
Liver Cancer
European Urology
European Urology Oncology
Neuro-Oncology
Blood
Leukemia
Blood Cancer Journal
Radiotherapy and Oncology
International Journal of Radiation Oncology, Biology, Physics
Breast Cancer Research and Treatment
Hematological Oncology
Journal of Neuro-Oncology
Diseases of the Colon & Rectum
The Journal of Pathology
Modern Pathology
International Journal of Gynecological Cancer
Journal of Surgical Oncology
The Breast
Clinical Lung Cancer
Pancreatology'''.splitlines()
CROSS = '''Nature
Science
Cell
The New England Journal of Medicine
The Lancet
JAMA
The BMJ
Nature Communications
Science Advances
Science Translational Medicine
Cell Reports Medicine
Cell Research
Nature Genetics
Genome Biology
Genome Medicine
Cell Genomics
Immunity
Cell Metabolism
Nature Biotechnology
Nature Biomedical Engineering
Nature Immunology
Nature Methods
Cell Systems
PNAS
eBioMedicine'''.splitlines()
all_journals=[]
for tier, group in [('core',TIER1),('oncology',TIER2),('specialist',SPECIALIST),('cross',CROSS)]:
    for j in group:
        all_journals.append({'name':j,'tier':tier, 'enabled':True, 'issn':None, 'letter_policy':'unverified'})
assert len({x['name'] for x in all_journals})==len(all_journals)
Path(__file__).with_name('journals.json').write_text(json.dumps({'version':'0.1','note':'Initial candidates only; journal metrics, ISSNs, current letter policies require independent verification.', 'journals':all_journals},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('journals',len(all_journals))
