"""PushPlus notification output, separate from article discovery.

One confirmed API send is tracked separately from article discovery. A
successful push API response does not guarantee delivery to a handset.
"""
import html
import json
import os
import urllib.request
import urllib.parse


def render_message(papers):
    out=['<h3>SCI Letter Scout｜新论文候选</h3>', '<p>仅为摘要初筛，不代表已发现研究错误。</p>']
    for p in papers:
        title=html.escape(p.get('title') or 'Untitled')
        journal=html.escape(p.get('journal') or 'Unknown journal')
        date=html.escape(p.get('online_date') or '待核对')
        score=str(p.get('priority_score') or '')
        u=p.get('url') or ('https://doi.org/'+p['doi'] if p.get('doi') else '')
        if not u.startswith(('https://','http://')):
            u=''
        angle=html.escape((p.get('ai') or {}).get('potential_letter_angle') or '尚未完成AI初筛；请查看原文与补充材料。')
        out.append(f'<p><b>{title}</b><br>期刊：{journal}<br>发表日期：{date}<br>阅读优先级：{score}/100<br>待核查角度：{angle}<br><a href="{html.escape(u,quote=True)}">打开原文或PubMed</a></p>')
    return ''.join(out)


def send_pushplus(papers):
    token=os.getenv('PUSHPLUS_TOKEN')
    if not token or not papers:
        return False
    payload={'token':token,'title':'SCI Letter Scout：发现新论文候选','content':render_message(papers),'template':'html','channel':'wechat'}
    topic=os.getenv('PUSHPLUS_TOPIC')
    if topic:
        payload['topic']=topic
    request=urllib.request.Request('https://www.pushplus.plus/send',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=20) as r:
            ans=json.load(r)
        # PushPlus documents code 200 as accepted; not handset delivery proof.
        good=(str(ans.get('code'))=='200')
        if not good:
            print('PushPlus API did not accept message; code:',ans.get('code'))
        return good
    except Exception as exc:
        print('PushPlus unavailable:',type(exc).__name__)
        return False


def send_serverchan(papers):
    """ServerChan Turbo free-tier compatible push (up to 5 requests/day).

    Only the remote private job can access SERVERCHAN_SENDKEY. Never print it,
    include it in a public feed, or ship it in an app package.
    """
    key=os.getenv('SERVERCHAN_SENDKEY','')
    if not key or not papers:
        return False
    # The free service notification card contains primarily a title. Put the
    # most important details in the title, and the report in the body.
    first=papers[0]
    journal=str(first.get('journal') or '肿瘤新论文')[:30]
    mixed=any(p.get('journal') != first.get('journal') for p in papers[1:])
    title=f'SCI Letter Scout：{len(papers)}篇｜{journal}{"等" if mixed else ""}'[:100]
    lines=['## SCI Letter Scout 新论文候选', '', '以下是待核查的线索，不代表原论文存在错误。', '']
    for paper in papers:
        name=str(paper.get('title') or 'Untitled').replace('\n',' ').strip()
        doi=str(paper.get('doi') or '').strip()
        url=str(paper.get('url') or ('https://doi.org/'+doi if doi else ''))
        if not url.startswith(('https://','http://')):
            url=''
        angle=str((paper.get('ai') or {}).get('potential_letter_angle') or '尚未完成AI初筛，请核查正文和补充材料。')
        lines += [f'### {name}', f'期刊：{paper.get("journal") or "待核对"}',
                  f'上线日期：{paper.get("online_date") or "待核对"}',
                  f'阅读优先级：{paper.get("priority_score") or 0}/100',
                  f'待核查切入点：{angle}']
        if doi:
            lines.append(f'DOI：{doi}')
        if url:
            lines.append(f'[阅读原文]({url})')
        lines.append('')
    endpoint='https://sctapi.ftqq.com/'+urllib.parse.quote(key,safe='')+'.send'
    payload=urllib.parse.urlencode({'title':title,'desp':'\n'.join(lines)}).encode('utf-8')
    req=urllib.request.Request(endpoint,data=payload,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            ans=json.load(r)
        ok=(str(ans.get('code'))=='0')
        if not ok:
            print('ServerChan API did not accept message, code:',ans.get('code'))
        return ok
    except Exception as exc:
        print('ServerChan unavailable:',type(exc).__name__)
        return False


def resolve_provider(configured='auto'):
    """Return a recognized provider; never fall back to a paid service."""
    if configured in ('serverchan','pushplus'):
        return configured
    if configured != 'auto':
        return 'none'
    if os.getenv('SERVERCHAN_SENDKEY'):
        return 'serverchan'
    if os.getenv('PUSHPLUS_TOKEN'):
        return 'pushplus'
    return 'none'


def send_notification(papers,provider):
    if provider=='serverchan':
        return send_serverchan(papers)
    if provider=='pushplus':
        return send_pushplus(papers)
    return False
