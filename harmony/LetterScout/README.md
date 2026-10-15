# SCI Letter Scout HarmonyOS App (development build)

Native ArkTS/ArkUI project for DevEco Studio 26.0.0. The current milestone compiles an unsigned HAP and displays the public paper feed from `data/feed.json` in the owner's GitHub repository.

Implemented: first-run onboarding for oncology and 13 NLM-catalogued anesthesiology journals, all-versus-selected journal subscriptions within the chosen specialty, local persistence of subscription settings and favorites, paper list, search by title/journal/DOI, abstract/detail view, manual refresh, an oncology priority threshold of 65, explicit evidence disclaimer, and network-error state. The Push Kit client scaffold now compiles: it requests notification consent after the page loads, obtains a Push Token without logging it, configures notification clicks to open the app, and registers one foreground notification listener. No Gemini key, ServerChan key or Huawei server credential is bundled. The specialty and journal choice filters the shared cloud feed on the device; it does not create a per-user cloud scan.

Not implemented yet: tappable article links, cloud-side per-user subscriptions, AI scheduled analysis, AppGallery Connect Push Kit activation, secure Push Token registration, the server-side Push API sender, in-app notification settings, release signing, physical-device Push testing, and AppGallery submission. The journal selection currently filters only this device's public feed. Do not publish this milestone as a finished app.

Open this project from an ASCII-only path in DevEco Studio. The build tool rejects the Chinese characters in the parent workspace path. The provisional bundle name is `com.sciletterscout.app`; replace it with the identity registered in AppGallery Connect before configuring Push Kit or release signing.

The feed URL is defined in `entry/src/main/ets/pages/Index.ets`. A public GitHub raw URL is convenient for development but may be unreliable on some networks. Production distribution needs an availability and privacy review.
