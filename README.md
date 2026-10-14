# SCI Letter Scout · 医学新论文 Letter 雷达 (developer preview 0.3)

**Free-first, self-hosted scholarly metadata monitoring for oncology and anesthesiology.** The current default performs public-metadata retrieval only: paid AI, WeChat delivery and automatic billing are disabled. A native HarmonyOS development client reads the public feed; Huawei Push Kit is not connected yet.

## What works in this prototype

- 100 **candidate** oncology/cross-disciplinary journals plus 13 NLM-catalogued anesthesiology titles in `config/journals.json` (not a certified JCR ranking; Letter policies and journal metrics still require verification).
- PubMed `crdt` polling of all enabled journal titles, where available; Crossref incremental checks of 12 rotating journal titles per run (the entire Crossref list is **not** scanned every 5 minutes).
- Metadata normalization, DOI-based deduplication, first-detection time, 72-hour Crossref indexed-date lookback, and a 45-day publication-age guard against old records that were merely reindexed.
- Reading-priority heuristic; **not** a claim that papers are wrong or likely to be accepted as Letters.
- Optional Gemini abstract-level JSON screening code remains available but is disabled in the default configuration because no usable zero-billing account has been verified for this deployment.
- `data/feed.json` is the **public, read-only** interface consumed by the HarmonyOS development app. It includes specialty tags, source health, configured-journal counts and explicit AI/Push status.
- A native ArkTS/ArkUI app compiles in DevEco Studio 26 and has run in the Huawei simulator. It supports specialty/journal onboarding, list/search/detail, local favorites and local settings.
- `SKILL.md` for agent analysis and `.opencode/skills/...` for OpenCode loading.

## What is NOT built yet

- Huawei Push Kit integration, secure device registration, secure remote changes of subscriptions from the phone, independent user sign-in, formal release signing, formal JCR/ISSN validation of the full oncology list, official journal-policy database, and live publisher Online First retrieval.
- Rigorous full-text/supplementary Letter review (needs a human and official journal policies).
- Proven 5-minute detection latency. Publisher feeds and schedule execution may lag; PubMed creation is not online-publication time.

## Free cloud deployment (public repository)

1. Create an empty **public** GitHub repo named `sci-letter-scout` and upload the contents. You can copy this repo to your own account; no personal API keys are included.
2. Under **Settings → Actions → General**, permit Actions and make sure workflow `GITHUB_TOKEN` can write repository contents (needed for history and public feed).
3. Optionally set the `CONTACT_EMAIL` repository variable for NCBI/Crossref API etiquette. Do not put API keys or personal data in the public repository or HarmonyOS package.
4. In GitHub **Actions → SCI Letter Scout → Run workflow**, test the flow and inspect logs. Scheduled scans then run on the default branch, nominally every 5 minutes UTC.
5. Read `data/feed.json` through the public raw GitHub URL used by the HarmonyOS app.

### Zero-spend safeguards

- The repository uses the standard `ubuntu-latest` runner in a **public** repo; public standard Actions runners are currently free. Private repos have different billing rules.
- The deployed workflow does not inject any AI or WeChat credentials. AI and external notifications are disabled in `config/settings.json`.
- Repeated scanning deduplicates DOI/PMID records. Rule-based discovery continues without any model account.
- Don't put unpublished papers, credentials, private notes or drafts into the public repo or free model input.

### Settings

Change `config/settings.json` for polling windows and rotation batch size. Change `config/journals.json` to enable/disable journal titles. The GitHub cron frequency is set in `.github/workflows/monitor.yml`. Do not enable AI or an external notification adapter until its billing and privacy behavior has been independently verified.

### Test locally without secrets

```sh
python -m unittest discover -s tests -v
SCOUT_DRY_RUN=1 python scan.py
```

The real fetch command requires internet access, and the current development environment did **not** conduct a live API or handset delivery test. To use the cloud system, deploy to your GitHub account and test with actual data. The mock tests are independent of external services.

### Operational design constraints

- GitHub schedules can be delayed/skipped and public repo schedules may be disabled after 60 days of inactivity.
- The Crossref rotating 12-of-113 check means a journal is generally revisited after ~50 minutes, not every 5 minutes; PubMed searches span all titles every run, subject to NCBI indexing delay. The public feed tags each newly found paper with `specialty`; historic papers without a tag are treated as oncology by the App.
- In journal list version 0.1, some journal naming variants will not match the exact publisher container title and will need ISSN resolution during the next phase.
- Per-scan state is committed to the repo; public feed shows bibliographic metadata. There are no protected medical records or personal manuscript content in the published feed.
- To avoid a misleading stream of commits, the repository heartbeat normally changes about once per hour if no articles were added.

## Next phase (roadmap)

1. Verify title/ISSN mapping, increase specialty coverage, add source timestamp accuracy and acceptance-policy checks.
2. Run a 24–72-hour real-data pilot on GitHub; compare against official Online First lists and tune alert quality/latency.
3. Add publisher Online First sources for a small high-priority set, then measure real detection latency.
4. Integrate Huawei Push Kit after AppGallery Connect configuration and a physical-device test are available.
5. Add safe cloud subscription synchronization and deeper review of user-selected full text/supplements. Human decision remains mandatory.

## Ethics and author policies

AI raises **questions to inspect**, it does not accuse. A Letter should not be submitted where the target journal prohibits AI-generated letters. Confirm current author guidelines before drafting, submitting or using AI for writing.

## License

MIT. No guarantee of uninterrupted service or acceptance of submitted Letters.
