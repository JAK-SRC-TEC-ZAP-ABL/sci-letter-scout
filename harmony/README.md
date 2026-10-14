# HarmonyOS client — working development project

The native ArkTS/ArkUI project is in `LetterScout/`. It compiles in DevEco Studio 26 and has run in the Huawei simulator. It is still a development build, not an AppGallery-ready release.

## Onboarding status
The app offers first-run specialty selection for oncology and anesthesiology, all-versus-selected journal choices, and a clear status page for AI and HarmonyOS notifications. Choices are persisted locally. They filter the shared public feed on the device; they do not alter the cloud scanner or enable AI/Push Kit.

## First four screens
- Latest articles
- Letter candidate report
- Bookmarks / submission tracking
- Settings + health

## Read-only remote feed V0.1
`https://raw.githubusercontent.com/<YOUR_ACCOUNT>/sci-letter-scout/main/data/feed.json`

Schema: `{ "schema_version": "0.3", "generated_at": "UTC timestamp or null", "subjects": ["oncology", "anesthesiology"], "journal_counts": {...}, "source_health": {...}, "ai_status": "disabled", "harmony_push_status": "not_configured", "papers": [{"doi":...,"title":...,"journal":...,"specialty":...,"online_date":...,"priority_score":...}] }`

Current feed is public. It MUST NOT contain secrets, personal drafts or private user preferences. The phone can filter articles locally. Cloud-side changes to journals and push frequency are NOT yet supported from the app. A future authenticated config synchronization service is required before enabling remote edits.

## Platform constraints
A native app cannot securely hold the administrator's Gemini, GitHub or PushPlus secrets. Store credentials in the owner's cloud deployment; never ship them in an App bundle or publish them in git.

A few-hundred-KB binary is an aspiration only; packaging size must be tested with DevEco Studio. Push Kit support and 2026 developer incentive eligibility require separate account, device and policy verification.
