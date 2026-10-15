"""Run with: python scan.py ; set SCOUT_DRY_RUN=1 to disable AI and push."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from src.ai import screen_abstract
from src.engine import fetch_pubmed, fetch_crossref, merge_papers, normalize_title, unique_id, utcnow
from src.notify import send_notification, resolve_provider

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DATA.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(path)


def specialty_round_robin(papers):
    """Prevent a busy specialty from filling every new-paper slot."""
    queues={}
    for paper in sorted(papers,key=lambda item:-item['priority_score']):
        queues.setdefault(paper['specialty'],[]).append(paper)
    while any(queues.values()):
        for queue in queues.values():
            if queue:
                yield queue.pop(0)


def run():
    conf=load_json(ROOT/'config/settings.json', {})
    journals=[j for j in load_json(ROOT/'config/journals.json',{'journals':[]})['journals'] if j.get('enabled',True)]
    specialty_by_journal={normalize_title(j['name']):j.get('specialty','oncology') for j in journals}
    state=load_json(DATA/'state.json',{'seen':{},'ai_calls_per_day':{},'sent':[],'last_scan':None})
    state.setdefault('seen',{})
    state.setdefault('ai_calls_per_day',{})
    state.setdefault('sent',[])
    state.setdefault('notify_attempts_by_day',{})
    today=utcnow().date().isoformat()
    # Keep 2 days of request accounting. Never use a missing or stale state to assume unlimited model quota.
    state['notify_attempts_by_day']={k:v for k,v in state['notify_attempts_by_day'].items() if k>=str(utcnow().date()-dt.timedelta(days=2))}
    state['ai_calls_per_day']={k:v for k,v in state['ai_calls_per_day'].items() if k>=str(utcnow().date()-dt.timedelta(days=2))}
    dry_run=os.getenv('SCOUT_DRY_RUN','0')=='1'
    collected=[]
    source_health={}
    try:
        collected.extend(fetch_pubmed(journals,days=conf['monitoring']['pubmed_created_days'],batch_size=conf['monitoring']['pubmed_batch_size']))
        source_health['pubmed']='ok'
    except Exception as exc:
        source_health['pubmed']='error:'+type(exc).__name__
        print('PubMed fetch error',type(exc).__name__)
    try:
        collected.extend(fetch_crossref(
            journals,
            hours=conf['monitoring']['crossref_indexed_hours'],
            per_run=conf['monitoring']['crossref_journals_per_run'],
            max_publication_age_days=conf['monitoring'].get('crossref_max_publication_age_days',45),
        ))
        source_health['crossref']='ok'
    except Exception as exc:
        source_health['crossref']='error:'+type(exc).__name__
        print('Crossref fetch error',type(exc).__name__)
    candidates=merge_papers(collected)
    for p in candidates:
        p['specialty']=specialty_by_journal.get(normalize_title(p.get('journal','')),'oncology')
    new=[]
    for p in specialty_round_robin(candidates):
        uid=unique_id(p)
        if uid and uid not in state['seen'] and len(new)<conf['monitoring']['max_new_per_run']:
            p['first_detected']=utcnow().isoformat()
            new.append(p)
    max_day=int(conf['ai'].get('max_calls_per_day',0))
    max_run=int(conf['ai'].get('max_calls_per_scan',0))
    used=state['ai_calls_per_day'].get(today,0)
    if conf['ai'].get('enabled') and not dry_run and os.getenv('GEMINI_API_KEY') and os.getenv('AI_FREE_TIER_ACK') == 'YES':
        for p in new[:max_run]:
            if used>=max_day:
                break
            # Count the attempt, even on failure, so retry loops cannot accidentally explode usage.
            used+=1
            p['ai']=screen_abstract(p,conf['ai']['model'])
        state['ai_calls_per_day'][today]=used
    for p in new:
        state['seen'][unique_id(p)]=p
    # Note: by design, notification failures remain eligible for a future retry.
    notify_cfg=conf['notifications']
    # Existing WeChat settings remain oncology-only; other specialties are app-feed data.
    not_sent=[p for p in state['seen'].values() if p.get('specialty','oncology')=='oncology' and unique_id(p) not in state['sent'] and p.get('priority_score',0)>=notify_cfg['score_threshold']]
    not_sent.sort(key=lambda p:(p.get('first_detected',''),p.get('priority_score',0)),reverse=True)
    batch=not_sent[:notify_cfg['max_messages_per_scan']]
    sent=False
    provider=resolve_provider(notify_cfg.get('channel','auto'))
    # ServerChan Turbo free tier: never attempt more calls than its configured
    # daily free quota. Count attempts, not only successes, so errors cannot
    # inadvertently exceed quota. Provider rate policy may change.
    count=state['notify_attempts_by_day'].get(today,{})
    day_limit=int(notify_cfg.get('serverchan_max_calls_per_day',5))
    can_attempt=provider!='none' and (provider!='serverchan' or count.get('serverchan',0)<day_limit)
    if notify_cfg.get('enabled') and not dry_run and batch and can_attempt:
        count[provider]=count.get(provider,0)+1
        state['notify_attempts_by_day'][today]=count
        sent=send_notification(batch,provider)
    if sent:
        state['sent'] = list(dict.fromkeys(state['sent']+[unique_id(p) for p in batch]))
    # Keep 90 days of past state; 100-day-old articles outside retry horizon can be pruned.
    cutoff=(utcnow()-dt.timedelta(days=90)).isoformat()
    state['seen']={k:v for k,v in state['seen'].items() if v.get('first_detected','')>=cutoff}
    live_keys=set(state['seen'])
    state['sent']=[k for k in state['sent'] if k in live_keys]
    # A heartbeat once per hour avoids hundreds of no-op commits per day.
    old_heartbeat=state.get('last_scan')
    needs_heartbeat=not old_heartbeat
    if old_heartbeat:
        try:
            needs_heartbeat=(utcnow()-dt.datetime.fromisoformat(old_heartbeat)).total_seconds() >= 3600
        except ValueError:
            needs_heartbeat=True
    if new or sent or needs_heartbeat or source_health != state.get('source_health'):
        state['last_scan']=utcnow().isoformat()
        state['source_health']=source_health
    public=sorted(state['seen'].values(),key=lambda p:p.get('first_detected',''),reverse=True)[:300]
    # Never expose tokens, local state accounting, or secret-bearing config in public JSON.
    journal_counts={}
    for journal in journals:
        specialty=journal.get('specialty','oncology')
        journal_counts[specialty]=journal_counts.get(specialty,0)+1
    write_json(DATA/'feed.json',{
        'schema_version':'0.3',
        'generated_at':state['last_scan'],
        'subjects':sorted(journal_counts),
        'journal_counts':journal_counts,
        'source_health':source_health,
        'ai_status':'disabled',
        'harmony_push_status':'not_configured',
        'papers':public,
    })
    write_json(DATA/'state.json',state)
    print(json.dumps({'journals_configured':len(journals),'source_health':source_health,'new_papers':len(new),'ai_attempts_today':used,'notification_accepted':sent,'notification_provider':provider,'feed_size':len(public)},ensure_ascii=False))
    if all(v.startswith('error:') for v in source_health.values()):
        raise RuntimeError('All retrieval sources failed; see source_health')

if __name__=='__main__':
    run()
