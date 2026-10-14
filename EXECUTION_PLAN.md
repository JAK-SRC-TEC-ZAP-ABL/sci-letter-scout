# SCI Letter Scout — 执行方案（个人肿瘤学优先 / 2026-10-14）

> 状态：**开发预览版 v0.1**。已具备可供本地模拟测试的 Python 监测核心、OpenCode Skill、GitHub Actions workflow、可编辑期刊候选表和微信 PushPlus 适配器。**未**部署到用户 GitHub，**未**获取真实 API 返回结果、**未**完成手机推送测试、**未**创建可安装的鸿蒙 HAP，更未通过应用商店审核。

## 0. 目标与不可退让的约束

- 第一目标：尽快发现高影响力肿瘤学新论文，找到**可验证**且有学术价值的 Letter to the Editor / Correspondence / Matters Arising 讨论机会，及时向个人微信提醒。
- 持续运行：电脑关机不影响 GitHub Actions 定时运行；默认每 5 分钟计划启动一次。该计划间隔**不**保证数据源已收录，也不保证每本期刊 5 分钟内轮询或信息送达。
- 免费优先：不绑自动扣费项目；模型免费额度尽时自动退回规则筛选；公开代码、私人密钥绝对隔离。
- 先满足个人肿瘤学需求，其他学科/其他用户独立部署作为未来扩展；不要因新增用户消耗作者个人免费额度。
- AI 基于标题摘要提出“值得核查的问题”，不能凭摘要声称原论文存在已证实错误。针对论文的正式意见必须根据原文与补充材料核对，并核实期刊现行 AI 政策。

## 1. 项目分层

1. **监测核心（Python）**：期刊候选列表→数据源增量拉取→规范化→DOI/PMID 去重→阅读优先级→本地状态与公开数据文件。
2. **可选 AI 初筛（Gemini 免费层）**：只对新增且符合规则的公开摘要调用；严格数量上限；JSON 格式输出研究类型、待核查问题、证据状态。
3. **消息通知（PushPlus/微信）**：高优先级新增论文发送即时提醒；重复发送抑制；可配置每日汇总与静默时段；失败重试。
4. **Agent Skill（SKILL.md / OpenCode）**：用于用户选定论文后的深入研读；引用具体图表/方法及补充材料；判断 Letter 是否值得写。其工作不要求云端 OpenCode 常驻。
5. **鸿蒙 App（ArkTS + ArkUI）**：仅展示云端结果、执行首次配置向导、本地筛选/收藏；不在 App 包内放 API Key；独立服务端同步配置为后续模块。

## 2. 分阶段任务与验收

### 阶段 A：监测核心校准（先做）
- [ ] 对已收集的 **100 本候选**期刊逐本校验官方名称、ISSN、所属领域、影响力和是否值得纳入；不是全部已经验证的 JCR 高分期刊。补齐核心肿瘤、器官专科、免疫、临床、基础机制、转化、综合顶刊，避免固定数量上限。
- [ ] 加入真实 ISSN 匹配、期刊同名变体、文章类型剔除规则；区分 `online_publication_date`、Crossref `indexed` 时间、PubMed `created` 日期与 `first_seen`。
- [ ] Crossref、PubMed 源的延时与失败状态独立统计，补上 OpenAlex 回溯发现；设计周期性 72 小时回补与每日完整回溯。
- [ ] 若摘要版权或再分发许可不明，公开 API 仅发布 DOI、标题、期刊、日期、短评估等可分享字段，不批量公开再发布第三方摘要正文。
- [ ] 对比 10—20 篇已知官网 Online First 论文，实际检验能否发现、首次发现延迟与遗漏率。
- **通过标准**：原始数据可追溯、可重启不重复入库，失败有日志，已知文章回放结果可核对。

### 阶段 B：GitHub 云端部署
- [ ] 创建本人名下**公开**仓库 `sci-letter-scout`，上传仓库文件并开启 Actions。
- [ ] 用 `workflow_dispatch` 手动运行一次，核对 `data/feed.json` 和日志；之后设定 `cron: '2/5 * * * *'`。
- [ ] 使用 `concurrency` 保护避免任务重叠；持久化 DOI 去重信息和上次成功检查点。
- [ ] 设置失败重试、运行异常报告、日常健康检查；监控 GitHub 定时延迟/缺失，不能承诺精确 5 分钟。
- **通过标准**：本地关机，GitHub 自动运行并留下可追溯数据；回放一次网络异常可恢复。

### 阶段 C：Gemini AI 与微信
- [ ] 在 Google AI Studio 的**实际免费项目**申请 Key，确认区域、型号和可用配额；不启用付费结算。保存为 GitHub Secret `GEMINI_API_KEY`。
- [ ] 设置变量 `AI_FREE_TIER_ACK=YES` 之前，确认密钥项目的结算状态；仍设置严格每日调用上限，避免误认变量本身能防止真实扣费。
- [ ] 用公开论文样本校准 AI JSON 分析；只允许建议/问题，不把缺少摘要信息变成批评结论。
- [ ] 申请符合免费资格的 PushPlus Token，关注微信对应服务，存入 Secret `PUSHPLUS_TOKEN`；先发送单条测试，再发送真实候选。
- [ ] 高优先级即时提醒、可选每日汇总、错误重试、冷却时间；单篇只发一次常规提醒；推送接口成功与手机真正收到需分别验证。
- **通过标准**：微信实际收到至少一条带真实 DOI 的提醒；AI 免费额度耗尽时，系统继续规则筛选且不产生付费调用。

### 阶段 D：鸿蒙 App 原生首版
- [ ] 使用 DevEco Studio 建 ArkTS/ArkUI 原生工程，不做只有 WebView 的空壳。
- [ ] **首次启动向导 7 步**：学科（默认肿瘤学）→推荐期刊与手动增删→扫描/播报频率区分→AI 筛选偏好→微信/其他通知渠道→个人云端绑定引导→测试和完成。
- [ ] **四个主页面**：最新论文、论文详情/AI 质控、收藏与写作状态、设置与运行健康信息。
- [ ] 只读数据接口先实现 `data/feed.json`；期刊配置的远程写回需要**有身份验证的服务端**，不能直接把 GitHub PAT/AI Key 写入公开 App，也不能只改本地 UI 却显示“云端已生效”。若远程配置暂未建好，应明确展示“待同步”，提供 GitHub 配置引导。
- [ ] Push Kit 作为可选升级，不依赖其通知频控来实现全部论文提醒；首版优先微信外部推送。优化 HAP 体积，但不保证几百 KB。
- **通过标准**：鸿蒙真机能安装、完成引导、读取真实结果、打开 DOI、收藏；所有控制如尚未联通云端，会如实说明。

### 阶段 E：发布和后续维护
- [ ] 先发布 GitHub `v1.0.0` Release（源码、安装部署说明、风险说明、测试报告），开源协议 MIT；个人密钥不能提交。
- [ ] 在华为开发者中心/AGC 建应用、实名状态检查、创建原生应用、完成签名/上传包、隐私政策与权限说明、填写资料与截图、提交审核。
- [ ] 核实中国大陆适用的备案/资质要求；确认第三方 SDK 收集信息的披露，明确本 App 是论文科研工具而非临床诊断工具。
- [ ] 2026 鸿蒙激励计划官网写明报名截至 2026-09-25、商户服务条件截至 2026-09-30；**2026-10-14** 已晚于上述日期。已提前报名者需自行登录后台确认资格，App 上架并不自动获得奖励。
- [ ] 后续升级：独立用户部署向导、其他专业期刊模板、更多推送渠道、云端偏好安全同步；**不**引入默认付费 SaaS。
- **通过标准**：GitHub Release 可下载、App 真机通过验收、AGC 审核通过后才称“已上架”。

## 3. 立即执行：个人绑定说明

1. GitHub 已有账号：新建公开空仓库 `sci-letter-scout`；将项目文件上传至默认分支；开启 Actions。
2. 仓库 **Settings → Secrets and variables → Actions**：
   - Secret `GEMINI_API_KEY`：Google AI Studio 生成，必须是可用的免费层项目。
   - Secret `PUSHPLUS_TOKEN`：PushPlus 微信推送的个人 Token，需满足其免费账号条件。
   - 可选 Secret `PUSHPLUS_TOPIC`：日后实验室扫码订阅话题使用。
   - Variable `AI_FREE_TIER_ACK=YES`：须由用户确认免费层且未启用计费后手动设置；该变量不是计费保险。
   - 可选 Variable `CONTACT_EMAIL`：科研检索 API 请求联系方式。
3. GitHub → **Actions** → `SCI Letter Scout` → **Run workflow**；检查运行日志、扫描摘要、通知发送结果；手动核验微信是否收到。
4. 确认第一轮真实数据与推送后，留云端监测运行，电脑可以关机。再开发鸿蒙 App。

## 4. 当前预览版实际状态

- 已完成：Python 监测框架、基础规则评分、DOI 去重、免费 AI 和微信适配的可选代码、GitHub 工作流、OpenCode Skill、100 本**候选**期刊配置。
- 已验证：13 项**模拟/离线**单元测试通过；未完成对真实数据源和微信接收的联调。
- 未完成：期刊权威核验、OpenAlex 数据源接入、完整投稿政策校对、真实云端运行、华为客户端工程与上架。

## 5. 官方文档入口

- GitHub Actions: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Gemini 免费价格: https://ai.google.dev/gemini-api/docs/pricing
- Google AI Studio API Key: https://aistudio.google.com/apikey
- PushPlus 免费额度: https://pushplus.plus/doc/guide/use.html
- 华为上架入口: https://developer.huawei.com/consumer/cn/appgallery/devstart/
- 鸿蒙激励计划 2026: https://developer.huawei.com/consumer/cn/activity/harmonyos-incentive/2026
- OpenCode Skills: https://dev.opencode.ai/docs/zh-cn/skills/


## 2026-10-14 · 零额外付费微信通道补充说明（v0.2）

- **Server酱 Turbo：优先零额外付费**。用微信扫码登录 https://sct.ftqq.com/ ，复制 `SCT` 开头的 SendKey，保存在 GitHub Actions 仓库 Secrets 的 `SERVERCHAN_SENDKEY`。免费版目前每天最多 5 条（API 请求），微信服务号可接收；微信消息卡片免费版一般只显示标题。
- **PushPlus：备选**。其“实名认证后每天 200 次免费微信推送”不代表新用户全程零费用：实名认证官方要求支付一次认证服务费，或购买会员。已经实名认证的账号可将消息 token 存为 `PUSHPLUS_TOKEN`。
- `config/settings.json` 的 `notifications.channel` 可以填 `auto` / `serverchan` / `pushplus`；`auto` 检测到 `SERVERCHAN_SENDKEY` 时优先用 Server酱。为了避免突破免费套餐，目前 Server酱每日发起请求数有 5 次硬限（包括失败请求）。
- **鸿蒙 App 不得保存或透传任何服务端发送密钥**。App 只显示公开的论文元数据与 AI 摘要，并引导用户在自己的 GitHub Secrets 中设置 AI 与通知密钥。发布的 APK/HAP、静态 JSON、README、Actions 日志不得包含密钥。
- 容错：免费套餐额度用尽时继续发现论文并积累候选结果，不触发付费服务；正式部署仍需以最新官方条款核验。
