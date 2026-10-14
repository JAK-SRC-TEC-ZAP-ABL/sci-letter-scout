# SCI Letter Scout · 肿瘤高分 Letter 论文雷达 (developer preview 0.2)

**Free-first, self-hosted scholarly metadata monitoring, optional Gemini abstract triage, and optional free ServerChan/WeChat alerts or PushPlus.** A prototype intended to be customized and tested on the owner's GitHub account. Does not assert that it has been deployed, connected to an AI account, or verified to deliver to a handset.

## What works in this prototype

- 100 **candidate** high-impact oncology, organ-specific, and cross-disciplinary journals in `config/journals.json` (not a certified JCR ranking; titles/ISSN/policies still require verification).
- PubMed `crdt` polling of all enabled journal titles, where available; Crossref incremental checks of 12 rotating journal titles per run (the entire Crossref list is **not** scanned every 5 minutes).
- Metadata normalization, DOI-based deduplication, first-detection time, 72-hour Crossref indexed-date lookback.
- Reading-priority heuristic; **not** a claim that papers are wrong or likely to be accepted as Letters.
- Optional Gemini abstract-level JSON screening, opt-in limits and graceful failure.
- Optional ServerChan Turbo 微信消息 (free tier currently 5/day) or PushPlus alerts (free sending requires account identity verification, which may incur a one-time charge). `data/feed.json` is a **public, read-only** JSON interface for a future HarmonyOS app.
- `SKILL.md` for agent analysis and `.opencode/skills/...` for OpenCode loading.

## What is NOT built yet

- A compiled HarmonyOS HAP, actual App UI, Huawei Push Kit integration, secure remote changes of subscriptions from the phone, independent user sign-in, formal JCR/ISSN journal validation, official journal-policy database, live publisher Online First scraping.
- Rigorous full-text/supplementary Letter review (needs a human and official journal policies).
- Proven 5-minute detection latency. Publisher feeds and schedule execution may lag; PubMed creation is not online-publication time.

## Free cloud deployment (public repository)

1. Create an empty **public** GitHub repo named `sci-letter-scout` and upload the contents. You can copy this repo to your own account; no personal API keys are included.
2. Under **Settings → Actions → General**, permit Actions and make sure workflow `GITHUB_TOKEN` can write repository contents (needed for history and public feed).
3. Under **Settings → Secrets and variables → Actions**, add `GEMINI_API_KEY` and **`SERVERCHAN_SENDKEY`** (ServerChan Turbo; 5 free WeChat notifications/day) as *Repository secrets* if you wish to use them. Alternatively use `PUSHPLUS_TOKEN` only if your PushPlus account has already satisfied its identity-verification requirement. DO NOT paste any secrets into the repo or the public HarmonyOS client.
4. Under *Repository variables*, add `AI_FREE_TIER_ACK=YES` **only after verifying the Gemini API key belongs to a project whose billing is disabled / free tier only**. Optionally set `CONTACT_EMAIL` (NCBI and Crossref etiquette). Otherwise AI is disabled even when a Key is provided.
5. For **zero additional spend**, visit [ServerChan Turbo](https://sct.ftqq.com/), log in via WeChat QR code, copy the SendKey (starts with `SCT`), then store it in GitHub as `SERVERCHAN_SENDKEY`. Its free tier allows 5 requests/day; the app caps attempts accordingly. If you already have an eligible PushPlus account, you may instead configure `PUSHPLUS_TOKEN`; the optional `PUSHPLUS_TOPIC` secret enables a topic. With neither token set, the scan continues without alerts.
6. In GitHub **Actions → SCI Letter Scout → Run workflow**, test the flow and inspect logs. Scheduled scans then run on the default branch, nominally every 5 minutes UTC.
7. Read `data/feed.json` via GitHub / raw file. Add the read-only remote URL to the HarmonyOS App when implemented.

### Zero-spend safeguards

- The repository uses the standard `ubuntu-latest` runner in a **public** repo; public standard Actions runners are currently free. Private repos have different billing rules.
- AI requests require both your API Key AND explicit `AI_FREE_TIER_ACK=YES`; the owner must independently confirm no billable project is linked. The code cannot certify Google's actual billing state; the acknowledgement does NOT itself guarantee $0 if the project's billing changes later.
- Application-side cap defaults to 25 Gemini calls/day and 4 per scan, ignoring articles already seen. When AI fails or quota is exhausted, rule-based discovery continues.
- Repeated scanning does not repeatedly notify an accepted DOI; failed push attempts can retry. PushPlus API acceptance is **not** proof of handset delivery.
- Don't put unpublished papers, credentials, private notes or drafts into the public repo or free model input.

### Settings

Change `config/settings.json` for polling rotation batch size, daily AI call budget, notification channel (`auto`, `serverchan`, or `pushplus`), ServerChan daily attempt cap and push priority threshold. Change `config/journals.json` to enable/disable journal titles. The GitHub cron frequency is set in `.github/workflows/monitor.yml`.

### Test locally without secrets

```sh
python -m unittest discover -s tests -v
SCOUT_DRY_RUN=1 python scan.py
```

The real fetch command requires internet access, and the current development environment did **not** conduct a live API or handset delivery test. To use the cloud system, deploy to your GitHub account and test with actual data. The mock tests are independent of external services.

### Operational design constraints

- GitHub schedules can be delayed/skipped and public repo schedules may be disabled after 60 days of inactivity.
- The Crossref rotating 12-of-100 check means a journal is generally revisited after ~45 minutes, not every 5 minutes; PubMed searches span all titles every run, subject to NCBI indexing delay.
- In journal list version 0.1, some journal naming variants will not match the exact publisher container title and will need ISSN resolution during the next phase.
- Per-scan state is committed to the repo; public feed shows bibliographic metadata. There are no protected medical records or personal manuscript content in the published feed.
- To avoid a misleading stream of commits, the repository heartbeat normally changes about once per hour if no articles were added.

## Next phase (roadmap)

1. Verify title/ISSN mapping, increase specialty coverage, add source timestamp accuracy and acceptance-policy checks.
2. Run a 24–72-hour real-data pilot on GitHub; compare against official Online First lists and tune alert quality/latency.
3. Implement the minimal HarmonyOS ArkTS/ArkUI app, seven-step onboarding and safe cloud config synchronization.
4. OpenCode skill deeper review of a user-selected PDF + supplemental material. Human decision remains mandatory.

## Ethics and author policies

AI raises **questions to inspect**, it does not accuse. A Letter should not be submitted where the target journal prohibits AI-generated letters. Confirm current author guidelines before drafting, submitting or using AI for writing.

## License

MIT. No guarantee of uninterrupted service or acceptance of submitted Letters.
