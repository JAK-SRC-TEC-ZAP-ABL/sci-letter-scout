import { common, OpenLinkOptions } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { http } from '@kit.NetworkKit';
import { preferences } from '@kit.ArkData';

const FEED_URL: string =
  'https://raw.githubusercontent.com/JAK-SRC-TEC-ZAP-ABL/sci-letter-scout/main/data/feed.json';
const JOURNALS_URL: string =
  'https://raw.githubusercontent.com/JAK-SRC-TEC-ZAP-ABL/sci-letter-scout/main/config/journals.json';
const BACKUP_FEED_URL: string =
  'https://sci-letter-scout-push-test.zhangyujian2025.workers.dev/public/feed.json';
const BACKUP_JOURNALS_URL: string =
  'https://sci-letter-scout-push-test.zhangyujian2025.workers.dev/public/journals.json';
const PRIVACY_URL: string =
  'https://github.com/JAK-SRC-TEC-ZAP-ABL/sci-letter-scout/blob/main/PRIVACY.md';

interface Journal {
  name: string;
  enabled: boolean;
  specialty?: string;
}

interface JournalCatalogue {
  journals: Journal[];
}

interface Paper {
  doi?: string;
  pmid?: string;
  title: string;
  journal: string;
  online_date: string;
  priority_score: number;
  abstract: string;
  url: string;
  evidence_level: string;
  letter_eligibility: string;
  specialty?: string;
  tier?: string;
  publication_types?: string[];
}

interface Feed {
  generated_at: string;
  papers: Paper[];
  source_health?: SourceHealth;
}

interface SourceHealth {
  pubmed?: string;
  crossref?: string;
}

@Entry
@Component
struct Index {
  @State private papers: Paper[] = [];
  @State private favoriteDois: string[] = [];
  @State private selectedPaper: Paper | null = null;
  @State private searchTerm: string = '';
  @State private showFavorites: boolean = false;
  @State private loading: boolean = false;
  @State private status: string = '正在读取论文数据…';
  @State private generatedAt: string = '';
  @State private sourceStatus: string = '';
  @State private freshnessStatus: string = '';
  @State private configured: boolean = false;
  @State private showSettings: boolean = false;
  @State private setupStep: number = 0;
  @State private selectedSpecialty: string = 'oncology';
  @State private allJournals: boolean = true;
  @State private selectedJournals: string[] = [];
  @State private availableJournals: string[] = [];
  @State private journalStatus: string = '正在读取期刊库…';
  @State private linkStatus: string = '';
  @State private policyStatus: string = '';
  private catalogueJournals: Journal[] = [];
  private settingsStore: preferences.Preferences | null = null;

  aboutToAppear(): void {
    this.loadSettings();
    this.loadJournals();
    this.refresh();
  }

  private loadSettings(): void {
    const context = this.getUIContext().getHostContext();
    if (!context) {
      return;
    }
    try {
      this.settingsStore = preferences.getPreferencesSync(context, { name: 'scout_settings' });
      this.configured = this.settingsStore.getSync('configured', false) as boolean;
      this.selectedSpecialty = this.settingsStore.getSync('specialty', 'oncology') as string;
      this.allJournals = this.settingsStore.getSync('all_journals', true) as boolean;
      const savedJournals = this.settingsStore.getSync('selected_journals', '[]') as string;
      const savedFavorites = this.settingsStore.getSync('favorite_dois', '[]') as string;
      this.selectedJournals = JSON.parse(savedJournals) as string[];
      this.favoriteDois = JSON.parse(savedFavorites) as string[];
    } catch (error) {
      this.configured = false;
      this.selectedSpecialty = 'oncology';
      this.allJournals = true;
      this.selectedJournals = [];
      this.favoriteDois = [];
    }
  }

  private saveSettings(): void {
    if (!this.settingsStore) {
      return;
    }
    try {
      this.settingsStore.putSync('configured', this.configured);
      this.settingsStore.putSync('specialty', this.selectedSpecialty);
      this.settingsStore.putSync('all_journals', this.allJournals);
      this.settingsStore.putSync('selected_journals', JSON.stringify(this.selectedJournals));
      this.settingsStore.putSync('favorite_dois', JSON.stringify(this.favoriteDois));
      this.settingsStore.flushSync();
    } catch (error) {
      this.journalStatus = '设置保存失败，请重试';
    }
  }

  private async readWithFallback(request: http.HttpRequest, primary: string, backup: string): Promise<http.HttpResponse> {
    try {
      const response = await request.request(primary, {
        method: http.RequestMethod.GET, connectTimeout: 8000, readTimeout: 10000
      });
      if (response.responseCode === 200) return response;
    } catch (error) {
      // A separate public endpoint may be reachable when GitHub is not.
    }
    return await request.request(backup, {
      method: http.RequestMethod.GET, connectTimeout: 8000, readTimeout: 10000
    });
  }

  private async loadJournals(): Promise<void> {
    const request = http.createHttp();
    try {
      const response = await this.readWithFallback(request, JOURNALS_URL, BACKUP_JOURNALS_URL);
      if (response.responseCode !== 200) {
        throw new Error(`HTTP ${response.responseCode}`);
      }
      const catalogue = JSON.parse(String(response.result)) as JournalCatalogue;
      if (!Array.isArray(catalogue.journals)) {
        throw new Error('期刊库格式不正确');
      }
      this.catalogueJournals = catalogue.journals;
      this.updateAvailableJournals();
      try {
        this.settingsStore?.putSync('cached_journals', String(response.result));
        this.settingsStore?.flushSync();
      } catch (error) {
        // A cache failure must not prevent use of the freshly downloaded catalogue.
      }
    } catch (error) {
      this.journalStatus = '无法读取期刊库，请检查网络后重试';
      try {
        const saved = this.settingsStore?.getSync('cached_journals', '') as string;
        if (saved) {
          const catalogue = JSON.parse(saved) as JournalCatalogue;
          if (Array.isArray(catalogue.journals)) {
            this.catalogueJournals = catalogue.journals;
            this.updateAvailableJournals();
            this.journalStatus = '正在使用之前保存的期刊库，可能不是最新版本';
          }
        }
      } catch (cacheError) {
        // Keep the network error visible when there is no usable cache.
      }
    } finally {
      request.destroy();
    }
  }

  private updateAvailableJournals(): void {
    this.availableJournals = this.catalogueJournals
      .filter((journal: Journal) => journal.enabled &&
        (journal.specialty || 'oncology') === this.selectedSpecialty && typeof journal.name === 'string')
      .map((journal: Journal) => journal.name);
    this.journalStatus = this.availableJournals.length > 0 ? '' : '该专业的云端期刊库尚不可用';
  }

  private chooseSpecialty(specialty: string): void {
    if (this.selectedSpecialty !== specialty) {
      this.selectedSpecialty = specialty;
      this.allJournals = true;
      this.selectedJournals = [];
      this.updateAvailableJournals();
    }
    this.setupStep = 1;
  }

  private async refresh(): Promise<void> {
    this.loading = true;
    this.status = '正在读取论文数据…';
    const request = http.createHttp();
    let failure: string = '无法连接论文数据源，请检查网络后重试';
    try {
      const response = await this.readWithFallback(request, FEED_URL, BACKUP_FEED_URL);
      if (response.responseCode !== 200) {
        failure = `论文数据源返回 HTTP ${response.responseCode}，请稍后重试`;
        throw new Error(`HTTP ${response.responseCode}`);
      }
      failure = '论文数据格式不正确，请稍后重试';
      const feed = JSON.parse(String(response.result)) as Feed;
      if (!Array.isArray(feed.papers)) {
        failure = '论文数据格式不正确，请稍后重试';
        throw new Error('论文数据格式不正确');
      }
      this.papers = feed.papers.filter((paper: Paper) =>
        typeof paper.title === 'string' && this.paperKey(paper).length > 0);
      this.generatedAt = feed.generated_at || '';
      this.updateSourceStatus(feed);
      this.status = this.papers.length === 0 ? '云端目前没有论文' : '';
      try {
        this.settingsStore?.putSync('cached_feed', String(response.result));
        this.settingsStore?.flushSync();
      } catch (error) {
        // A cache failure must not hide successfully downloaded papers.
      }
    } catch (error) {
      const networkCode = (error as BusinessError).code;
      if (failure === '无法连接论文数据源，请检查网络后重试' && typeof networkCode === 'number') {
        failure = `${failure}（错误码 ${networkCode}）`;
      }
      this.status = this.papers.length > 0 ? `${failure}。当前显示之前读取的数据，可能不是最新论文` : failure;
      try {
        const saved = this.settingsStore?.getSync('cached_feed', '') as string;
        if (saved) {
          const feed = JSON.parse(saved) as Feed;
          if (Array.isArray(feed.papers)) {
            this.papers = feed.papers.filter((paper: Paper) =>
              typeof paper.title === 'string' && this.paperKey(paper).length > 0);
            this.generatedAt = feed.generated_at || '';
            this.updateSourceStatus(feed);
            this.status = `${failure}。当前显示上次保存的数据，可能不是最新论文`;
          }
        }
      } catch (cacheError) {
        // Leave the failure visible if the saved data cannot be read.
      }
    } finally {
      request.destroy();
      this.loading = false;
    }
  }

  private updateSourceStatus(feed: Feed): void {
    const generated = Date.parse(feed.generated_at || '');
    if (Number.isNaN(generated)) {
      this.freshnessStatus = '无法确认数据生成时间，请核查云端运行状态';
    } else if (generated > Date.now() + 5 * 60 * 1000) {
      this.freshnessStatus = '数据生成时间晚于设备时间，请检查设备时间';
    } else if (Date.now() - generated > 2 * 60 * 60 * 1000) {
      this.freshnessStatus = '数据已超过两小时未更新，请检查云端运行状态';
    } else {
      this.freshnessStatus = '';
    }
    const source = feed.source_health;
    if (!source || !source.pubmed || !source.crossref) {
      this.sourceStatus = '文献来源状态未提供，请留意数据生成时间';
    } else if (source.pubmed !== 'ok' || source.crossref !== 'ok') {
      this.sourceStatus = `文献来源异常：PubMed ${source.pubmed === 'ok' ? '正常' : '异常'}，Crossref ${source.crossref === 'ok' ? '正常' : '异常'}；可能漏检`;
    } else {
      this.sourceStatus = '';
    }
  }

  private paperKey(paper: Paper): string {
    if (typeof paper.doi === 'string' && paper.doi.trim().length > 0) {
      return paper.doi;
    }
    return typeof paper.pmid === 'string' && paper.pmid.trim().length > 0 ? `pmid:${paper.pmid}` : '';
  }

  private visiblePapers(): Paper[] {
    const query = this.searchTerm.trim().toLowerCase();
    return this.papers.filter((paper: Paper) => {
      if ((paper.specialty || 'oncology') !== this.selectedSpecialty) {
        return false;
      }
      if (!this.allJournals && !this.selectedJournals.includes(paper.journal)) {
        return false;
      }
      if (this.showFavorites && !this.favoriteDois.includes(this.paperKey(paper))) {
        return false;
      }
      return query.length === 0 ||
        paper.title.toLowerCase().includes(query) ||
        paper.journal.toLowerCase().includes(query) ||
        (paper.doi || '').toLowerCase().includes(query) ||
        (paper.pmid || '').toLowerCase().includes(query);
    });
  }

  private toggleFavorite(doi: string): void {
    if (this.favoriteDois.includes(doi)) {
      this.favoriteDois = this.favoriteDois.filter((item: string) => item !== doi);
    } else {
      this.favoriteDois = [...this.favoriteDois, doi];
    }
    this.saveSettings();
  }

  private toggleJournal(name: string): void {
    if (this.selectedJournals.includes(name)) {
      this.selectedJournals = this.selectedJournals.filter((item: string) => item !== name);
    } else {
      this.selectedJournals = [...this.selectedJournals, name];
    }
  }

  private finishSetup(): void {
    if (!this.allJournals && this.selectedJournals.length === 0) {
      this.journalStatus = '请至少选择一本期刊';
      return;
    }
    this.configured = true;
    this.showSettings = false;
    this.saveSettings();
  }

  private paperLink(paper: Paper): string {
    const doi = (paper.doi || '').trim();
    if (/^10\.\d{4,9}\/\S+$/i.test(doi)) {
      return `https://doi.org/${encodeURI(doi)}`;
    }
    const url = (paper.url || '').trim();
    return /^https:\/\/[^\s/@]+(?:\/|$)/i.test(url) ? url : '';
  }

  private openPaper(paper: Paper): void {
    const link = this.paperLink(paper);
    if (!link) {
      this.linkStatus = '这篇论文暂无有效的原文链接';
      return;
    }
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    const options: OpenLinkOptions = { appLinkingOnly: false };
    this.linkStatus = '';
    try {
      context.openLink(link, options).catch((_error: BusinessError) => {
        this.linkStatus = '无法打开链接，请检查浏览器和网络';
      });
    } catch (_error) {
      this.linkStatus = '无法打开链接，请检查浏览器和网络';
    }
  }

  private openPrivacyPolicy(): void {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    const options: OpenLinkOptions = { appLinkingOnly: false };
    this.policyStatus = '';
    try {
      context.openLink(PRIVACY_URL, options).catch((_error: BusinessError) => {
        this.policyStatus = '暂时无法打开隐私政策，请检查浏览器和网络';
      });
    } catch (_error) {
      this.policyStatus = '暂时无法打开隐私政策，请检查浏览器和网络';
    }
  }

  @Builder
  private setupWizard() {
    Column({ space: 18 }) {
      Text(this.showSettings ? '修改订阅' : '欢迎使用 SCI Letter Scout')
        .fontSize(25)
        .fontWeight(FontWeight.Bold)
        .fontColor('#18303D')
        .width('100%')
      Text(`步骤 ${this.setupStep + 1} / 3`)
        .fontSize(13)
        .fontColor('#667085')
        .width('100%')

      if (this.setupStep === 0) {
        Text('请选择研究专业')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .width('100%')
        Button('肿瘤学 · 已接入')
          .backgroundColor('#155D70')
          .width('100%')
          .onClick(() => { this.chooseSpecialty('oncology'); })
        Button('麻醉学 · 13 本期刊')
          .backgroundColor('#155D70')
          .width('100%')
          .onClick(() => { this.chooseSpecialty('anesthesiology'); })
        Text('其他医学专业将逐步接入；这里仅开放云端实际扫描的专业。')
          .fontSize(14)
          .fontColor('#667085')
          .width('100%')
      } else if (this.setupStep === 1) {
        Text(this.selectedSpecialty === 'oncology' ? '选择肿瘤学期刊' : '选择麻醉学期刊')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .width('100%')
        Row({ space: 10 }) {
          Button('全部期刊')
            .backgroundColor(this.allJournals ? '#155D70' : '#E7F2F3')
            .fontColor(this.allJournals ? '#FFFFFF' : '#155D70')
            .onClick(() => { this.allJournals = true; })
          Button('指定期刊')
            .backgroundColor(this.allJournals ? '#E7F2F3' : '#155D70')
            .fontColor(this.allJournals ? '#155D70' : '#FFFFFF')
            .onClick(() => { this.allJournals = false; })
        }
        .width('100%')
        Text(this.allJournals ? '展示云端期刊库中符合筛选条件的论文。' :
          `已选择 ${this.selectedJournals.length} 本期刊`)
          .fontSize(13)
          .fontColor('#667085')
          .width('100%')
        if (!this.allJournals) {
          if (this.journalStatus.length > 0) {
            Text(this.journalStatus)
              .fontSize(13)
              .fontColor('#A04B2C')
              .width('100%')
          }
          Button('重新读取期刊库')
            .backgroundColor('#E7F2F3')
            .fontColor('#155D70')
            .onClick(() => { this.loadJournals(); })
          Scroll() {
            Column({ space: 8 }) {
              ForEach(this.availableJournals, (name: string) => {
                Row() {
                  Text(name)
                    .fontSize(14)
                    .fontColor('#1C2733')
                  Blank()
                  Text(this.selectedJournals.includes(name) ? '已选' : '选择')
                    .fontSize(13)
                    .fontColor('#155D70')
                }
                .padding(14)
                .width('100%')
                .backgroundColor(this.selectedJournals.includes(name) ? '#DCF0EE' : Color.White)
                .borderRadius(10)
                .onClick(() => { this.toggleJournal(name); })
              }, (name: string) => name)
            }
            .width('100%')
          }
          .layoutWeight(1)
        }
        Text('期刊库是候选名单；期刊指标、ISSN 与 Letter 投稿政策尚待逐一核验。')
          .fontSize(12)
          .fontColor('#667085')
          .width('100%')
        Button('下一步')
          .backgroundColor('#155D70')
          .enabled(this.allJournals || this.selectedJournals.length > 0)
          .onClick(() => { this.setupStep = 2; })
      } else {
        Text('分析与提醒')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .width('100%')
        Text('云端论文扫描：使用 GitHub Actions 计划运行，可能延迟。')
          .fontSize(15)
          .width('100%')
        Text('AI 定时审查：尚未启用。当前没有可用的免费 AI 服务凭证，不能在手机上设置后假装已经运行。')
          .fontSize(15)
          .fontColor('#775D2A')
          .padding(15)
          .backgroundColor('#FFF4D8')
          .borderRadius(12)
          .width('100%')
        Text('鸿蒙通知：需接入 Push Kit 与安全的设备登记服务后才能启用。')
          .fontSize(15)
          .width('100%')
        Text('专业与期刊选择只过滤本机看到的论文，不会修改云端统一扫描任务；鸿蒙系统通知尚未接入。')
          .fontSize(13)
          .fontColor('#667085')
          .width('100%')
        Button('完成设置，查看论文')
          .backgroundColor('#155D70')
          .width('100%')
          .onClick(() => { this.finishSetup(); })
      }

      if (this.setupStep > 0) {
        Button('上一步')
          .backgroundColor('#E7F2F3')
          .fontColor('#155D70')
          .onClick(() => { this.setupStep -= 1; })
      }
      Button('查看隐私政策')
        .backgroundColor('#E7F2F3')
        .fontColor('#155D70')
        .onClick(() => { this.openPrivacyPolicy(); })
      if (this.policyStatus.length > 0) {
        Text(this.policyStatus)
          .fontSize(13)
          .fontColor('#A04B2C')
          .width('100%')
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  private paperCard(paper: Paper) {
    Column({ space: 10 }) {
      Row() {
        Text(paper.journal || '未标注期刊')
          .fontSize(13)
          .fontColor('#16677A')
          .fontWeight(FontWeight.Bold)
        Blank()
        Text(`优先级 ${paper.priority_score ?? '—'}`)
          .fontSize(12)
          .fontColor('#667085')
      }
      .width('100%')

      Text(paper.title)
        .fontSize(16)
        .fontWeight(FontWeight.Medium)
        .fontColor('#1C2733')
        .maxLines(3)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .width('100%')

      if (paper.tier === 'cross') {
        Text('综合期刊文章：是否属于所选专业需核查')
          .fontSize(12)
          .fontColor('#8A4B08')
          .width('100%')
      }

      if (paper.publication_types && paper.publication_types.length > 0) {
        Text(`PubMed 文章类型：${paper.publication_types.join('、')}`)
          .fontSize(12)
          .fontColor('#667085')
          .width('100%')
      }

      Text(`${paper.online_date || '日期待核查'}  ·  ${paper.doi ? `DOI: ${paper.doi}` : `PMID: ${paper.pmid || '待核查'}`}`)
        .fontSize(12)
        .fontColor('#667085')
        .maxLines(2)
        .width('100%')

      Row({ space: 12 }) {
        Button('查看摘要')
          .fontSize(13)
          .backgroundColor('#155D70')
          .onClick(() => {
            this.linkStatus = '';
            this.selectedPaper = paper;
          })
        Button(this.favoriteDois.includes(this.paperKey(paper)) ? '已收藏' : '收藏')
          .fontSize(13)
          .fontColor('#155D70')
          .backgroundColor('#E7F2F3')
          .onClick(() => { this.toggleFavorite(this.paperKey(paper)); })
      }
      .width('100%')
    }
    .padding(16)
    .width('100%')
    .backgroundColor(Color.White)
    .borderRadius(16)
  }

  @Builder
  private detail(paper: Paper) {
    Column({ space: 16 }) {
      Row() {
        Button('返回')
          .backgroundColor('#E7F2F3')
          .fontColor('#155D70')
          .onClick(() => { this.selectedPaper = null; })
        Blank()
        Button(this.favoriteDois.includes(this.paperKey(paper)) ? '取消收藏' : '收藏')
          .backgroundColor('#155D70')
          .onClick(() => { this.toggleFavorite(this.paperKey(paper)); })
      }
      .width('100%')

      Scroll() {
        Column({ space: 15 }) {
          Text(paper.journal || '期刊待核查')
            .fontSize(14)
            .fontColor('#16677A')
            .width('100%')
          Text(paper.title)
            .fontSize(23)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1C2733')
            .width('100%')
          Text(`上线日期：${paper.online_date || '待核查'}`)
            .fontSize(14)
            .fontColor('#667085')
            .width('100%')
          Text(paper.doi ? `DOI：${paper.doi}` : `PMID：${paper.pmid || '待核查'}（DOI 尚未收录）`)
            .fontSize(14)
            .fontColor('#155D70')
            .width('100%')
          Text('摘要')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          Text(paper.abstract || '暂无摘要，请查看原文。')
            .fontSize(15)
            .lineHeight(24)
            .fontColor('#344054')
            .width('100%')
          Text('当前为文献线索，不代表原论文存在错误。Letter 切入点需核查全文、补充材料及期刊政策。')
            .fontSize(13)
            .fontColor('#775D2A')
            .padding(14)
            .backgroundColor('#FFF4D8')
            .borderRadius(10)
            .width('100%')
          Button('打开原文 / DOI')
            .backgroundColor('#155D70')
            .enabled(this.paperLink(paper).length > 0)
            .onClick(() => { this.openPaper(paper); })
          if (this.linkStatus.length > 0) {
            Text(this.linkStatus)
              .fontSize(13)
              .fontColor('#A04B2C')
              .width('100%')
          }
          Text(`原文链接：${this.paperLink(paper) || '暂无'}`)
            .fontSize(12)
            .fontColor('#667085')
            .width('100%')
        }
        .width('100%')
      }
      .layoutWeight(1)
    }
    .width('100%')
    .height('100%')
  }

  build() {
    Column({ space: 16 }) {
      if (!this.configured || this.showSettings) {
        this.setupWizard()
      } else if (this.selectedPaper) {
        this.detail(this.selectedPaper)
      } else {
        Row() {
          Column({ space: 3 }) {
            Text('SCI Letter Scout')
              .fontSize(25)
              .fontWeight(FontWeight.Bold)
              .fontColor('#18303D')
            Text(this.selectedSpecialty === 'oncology' ? '肿瘤新论文雷达' : '麻醉新论文雷达')
              .fontSize(13)
              .fontColor('#667085')
          }
          Blank()
          Button(this.loading ? '读取中' : '刷新')
            .fontSize(13)
            .backgroundColor('#155D70')
            .enabled(!this.loading)
            .onClick(() => { this.refresh(); })
          Button('设置')
            .fontSize(13)
            .backgroundColor('#E7F2F3')
            .fontColor('#155D70')
            .onClick(() => {
              this.setupStep = 0;
              this.showSettings = true;
            })
        }
        .width('100%')

        TextInput({ placeholder: '搜索标题、期刊或 DOI', text: this.searchTerm })
          .height(44)
          .backgroundColor(Color.White)
          .borderRadius(10)
          .onChange((value: string) => { this.searchTerm = value; })

        Row({ space: 10 }) {
          Button('最新论文')
            .backgroundColor(this.showFavorites ? '#E7F2F3' : '#155D70')
            .fontColor(this.showFavorites ? '#155D70' : '#FFFFFF')
            .onClick(() => { this.showFavorites = false; })
          Button('我的收藏')
            .backgroundColor(this.showFavorites ? '#155D70' : '#E7F2F3')
            .fontColor(this.showFavorites ? '#FFFFFF' : '#155D70')
            .onClick(() => { this.showFavorites = true; })
        }
        .width('100%')

        if (this.status.length > 0) {
          Text(this.status)
            .fontSize(14)
            .fontColor('#667085')
            .width('100%')
        }

        if (this.generatedAt.length > 0) {
          Text(`数据生成时间：${this.generatedAt}`)
            .fontSize(12)
            .fontColor('#667085')
            .width('100%')
        }

        if (this.sourceStatus.length > 0) {
          Text(this.sourceStatus)
            .fontSize(12)
            .fontColor('#8A4B08')
            .width('100%')
        }

        if (this.freshnessStatus.length > 0) {
          Text(this.freshnessStatus)
            .fontSize(12)
            .fontColor('#8A4B08')
            .width('100%')
        }

        Scroll() {
          Column({ space: 12 }) {
            ForEach(this.visiblePapers(), (paper: Paper) => {
              this.paperCard(paper)
            }, (paper: Paper) => this.paperKey(paper))
            if (this.visiblePapers().length === 0 && !this.loading && this.status.length === 0) {
              Text(this.showFavorites ? '还没有收藏论文' : '没有匹配的论文')
                .fontSize(14)
                .fontColor('#667085')
                .padding(20)
            }
          }
          .width('100%')
        }
        .layoutWeight(1)

        Text('数据来自公开论文元数据；推荐分数不是论文质量或 Letter 录用概率。')
          .fontSize(11)
          .fontColor('#98A2B3')
          .width('100%')
        Row() {
          Button('隐私政策')
            .fontSize(11)
            .fontColor('#155D70')
            .backgroundColor('#E7F2F3')
            .onClick(() => { this.openPrivacyPolicy(); })
          if (this.policyStatus.length > 0) {
            Text(this.policyStatus)
              .fontSize(11)
              .fontColor('#A04B2C')
          }
        }
        .width('100%')
      }
    }
    .padding(16)
    .width('100%')
    .height('100%')
    .backgroundColor('#F7F9FC')
  }
}

