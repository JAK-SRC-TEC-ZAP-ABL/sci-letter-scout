# HarmonyOS client — design contract (not yet a compiled App)

The current release focuses on a working oncology watcher. This folder defines the contract for a subsequent lightweight **ArkTS + ArkUI** client and avoids pretending an installable `.hap` exists.

## Onboarding (planned)
1. Select specialty (oncology default)
2. Review recommended journals (tier, user-selected, search by name)
3. Select notifications (cloud polling is administrator-configured; alert cadence is user-configurable)
4. Select AI relevance strictness and topics
5. Select multiple notification destinations (PushPlus/WeCom/DingTalk in future)
6. Connect **your own** GitHub + free-tier AI + push credentials, via instructions and secure external authorization
7. Run validation, then enter the app

## First four screens
- Latest articles
- Letter candidate report
- Bookmarks / submission tracking
- Settings + health

## Read-only remote feed V0.1
`https://raw.githubusercontent.com/<YOUR_ACCOUNT>/sci-letter-scout/main/data/feed.json`

Schema: `{ "generated_at": "UTC timestamp or null", "subject": "oncology", "papers": [{"doi":...,"title":...,"journal":...,"online_date":...,"priority_score":...,"ai":...}] }`

Current feed is public. It MUST NOT contain secrets, personal drafts or private user preferences. The phone can filter articles locally. Cloud-side changes to journals and push frequency are NOT yet supported from the app. A future authenticated config synchronization service is required before enabling remote edits.

## Platform constraints
A native app cannot securely hold the administrator's Gemini, GitHub or PushPlus secrets. Store credentials in the owner's cloud deployment; never ship them in an App bundle or publish them in git.

A few-hundred-KB binary is an aspiration only; packaging size must be tested with DevEco Studio. Push Kit support and 2026 developer incentive eligibility require separate account, device and policy verification.
