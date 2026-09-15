"""Optional one-shot RunningHub adapter. Only submit creates a paid task.
No automatic retries, polling loop, GPU upgrade, or background queue.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import requests
from studio import read, write, sha256, inspect_graph, local


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_text(value):
    text = str(value or '')
    key = os.environ.get('RUNNINGHUB_API_KEY', '')
    if key: text = text.replace(key, '[REDACTED]')
    return re.sub(r'https?://\S+', '[URL omitted]', text)[:2500]


def update(path, data):
    pending=path.with_name(path.name+'.tmp')
    pending.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(pending,path)


class Client:
    def __init__(self):
        self.key=os.environ.get('RUNNINGHUB_API_KEY','')
        self.host=os.environ.get('RUNNINGHUB_BASE','https://www.runninghub.cn').rstrip('/')
        if not self.key: raise ValueError('Set RUNNINGHUB_API_KEY locally; do not paste it into chat or files.')
        if self.host not in ('https://www.runninghub.cn','https://www.runninghub.ai'):
            raise ValueError('This adapter supports only the official .cn and .ai hosts.')
    def post(self, endpoint, body):
        r=requests.post(self.host+endpoint,headers={'Authorization':'Bearer '+self.key},
                        json=body,timeout=(15,90),allow_redirects=False)
        if r.status_code != 200: raise RuntimeError(f'HTTP {r.status_code}; request not automatically retried.')
        return r.json()
    def upload(self,path):
        with path.open('rb') as f:
            r=requests.post(self.host+'/openapi/v2/media/upload/binary',
                            headers={'Authorization':'Bearer '+self.key},files={'file':(path.name,f)},
                            timeout=(15,120),allow_redirects=False)
        if r.status_code!=200: raise RuntimeError(f'Upload HTTP {r.status_code}.')
        j=r.json()
        if j.get('code')!=0 or not j.get('data',{}).get('fileName'):
            raise RuntimeError('Upload failed: '+safe_text(j.get('message',j.get('msg'))))
        return j['data']['fileName']


def check_job(job):
    job=Path(job).resolve(); spec=read(job/'job.json')
    for name,digest in spec['hashes'].items():
        if sha256(local(job,name))!=digest: raise ValueError('Frozen input changed: '+name)
    graph=read(local(job,spec['graph']))
    inspect_graph(graph,'delivery')
    return spec,graph


def authorization(job,approval):
    p=read(approval)
    if (p.get('execution_allowed') is not True or type(p.get('max_new_tasks')) is not int or p['max_new_tasks']!=1
            or type(p.get('approved_rh_coins')) not in (int,float)
            or not math.isfinite(p['approved_rh_coins']) or p['approved_rh_coins']<=0 or not p.get('user_authorization_note')):
        raise ValueError('One-job authorization is missing. Read docs/starter/04-RunningHub.md.')
    if p.get('job_sha256')!=sha256(job/'job.json'):
        raise ValueError('Approval must identify the SHA256 of this exact job.json.')
    if p.get('instance_type') not in ('default','plus'):
        raise ValueError('Explicit instance_type default/plus is required.')
    return p


def submit(job,approval,workflow_id,client_factory=Client):
    job=Path(job).resolve(); spec,graph=check_job(job); auth=authorization(job,approval)
    if not re.fullmatch(r'\d+',workflow_id): raise ValueError('Use a workflow ID you own or are authorized to use.')
    statepath=job/'rh-state.json'
    if statepath.exists(): raise ValueError('Submission record exists. Query/recover it; do not pay for a duplicate.')
    # This durable intent predates any network request, including upload.
    state=dict(id=spec['id'],at=now(),status='PREPARING',task_id=None,
               instance_type=auth['instance_type'],approved_rh_coins=auth['approved_rh_coins'],
               fee_rh_coins=None,approval_sha256=sha256(approval),job_sha256=sha256(job/'job.json'),
               create_attempted=False)
    write(statepath,state)
    try:
        client=client_factory()
        graph['9']['inputs']['image']=client.upload(local(job,spec['image']))
        graph['10']['inputs']['audio']=client.upload(local(job,spec['drive']))
        inspect_graph(graph,'delivery')
        write(job/'submitted.api.json',graph)
        # The key lives in memory only. Complete graph is a documented advanced-API field.
        body={'apiKey':client.key,'workflowId':workflow_id,'workflow':json.dumps(graph,ensure_ascii=False),
              'addMetadata':False}
        if auth['instance_type']=='plus': body['instanceType']='plus'
        state.update(status='SUBMITTING',create_attempted=True); update(statepath,state)
        reply=client.post('/task/openapi/create',body)
        data=reply.get('data') or {}
        tid=data.get('taskId')
        state.update(response_code=reply.get('code'),response_message=safe_text(reply.get('msg')),
                     task_id=str(tid) if tid else None,
                     status=data.get('taskStatus','QUEUED') if tid else 'REJECTED_OR_UNCERTAIN')
        update(statepath,state)
        if not tid: raise RuntimeError('No taskId returned. Check the RH account before making another attempt.')
        return state
    except Exception as e:
        state.update(error=safe_text(e),status='SUBMIT_UNCERTAIN' if state['create_attempted'] and not state['task_id'] else state['status'])
        update(statepath,state)
        raise


def recover(job,task_id):
    job=Path(job).resolve(); p=job/'rh-state.json'; state=read(p)
    if not re.fullmatch(r'\d+',task_id): raise ValueError('Invalid task ID.')
    if state.get('task_id') and state['task_id']!=task_id: raise ValueError('Existing task ID differs; preserve this attempt.')
    state.update(task_id=task_id,status='RECOVERED_PENDING_QUERY',recovered_at=now())
    update(p,state)
    return state


def query(job,download=False,client_factory=Client):
    job=Path(job).resolve(); p=job/'rh-state.json'; state=read(p)
    if not state.get('task_id'): raise ValueError('No task ID. Locate the actual task in your RH account, then recover it.')
    client=client_factory(); result=client.post('/openapi/v2/query',{'taskId':state['task_id']})
    if result.get('taskId') and str(result['taskId'])!=state['task_id']: raise ValueError('Task ID mismatch.')
    usage=result.get('usage') or {}
    state.update(queried_at=now(),status=result.get('status','UNKNOWN'),
                 error_code=result.get('errorCode'),error=safe_text(result.get('errorMessage')))
    if usage.get('consumeCoins') is not None: state['fee_rh_coins']=usage['consumeCoins']
    update(p,state)  # No URLs or credentials are saved.
    if download and state['status']=='SUCCESS':
        candidates=[x for x in (result.get('results') or [])
                    if str(x.get('outputType','')).lower()=='mp4'
                    or urlsplit(x.get('url','')).path.lower().endswith('.mp4')]
        if len(candidates)!=1: raise ValueError('Expected exactly one MP4; inspect the authorized task outputs manually.')
        url=candidates[0]['url']
        if urlsplit(url).scheme!='https': raise ValueError('Expected HTTPS output URL.')
        out=job/'native.mp4'
        if out.exists():
            if state.get('native_sha256')!=sha256(out): raise ValueError('Unverified existing native.mp4; preserve and inspect it.')
        else:
            partial=job/'native.download-part'
            if partial.exists(): raise ValueError('Incomplete download exists. Inspect/move that partial file and download again; no resubmission.')
            with requests.get(url,stream=True,timeout=(15,120)) as r:
                r.raise_for_status()
                with partial.open('xb') as f:
                    for chunk in r.iter_content(1024*1024): f.write(chunk)
            os.link(partial,out); partial.unlink()
            state.update(native_sha256=sha256(out),downloaded_at=now()); update(p,state)
    return state


def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='action',required=True)
    for action in ('submit','query','download','recover'):
        p=sub.add_parser(action); p.add_argument('--job',type=Path,required=True)
        if action=='submit':
            p.add_argument('--approval',type=Path,required=True); p.add_argument('--workflow-id',required=True)
        if action=='recover': p.add_argument('--task-id',required=True)
    a=ap.parse_args()
    try:
        if a.action=='submit': r=submit(a.job,a.approval,a.workflow_id)
        elif a.action=='recover': r=recover(a.job,a.task_id)
        else: r=query(a.job,a.action=='download')
        print(json.dumps(r,ensure_ascii=False,indent=2))
    except Exception as e: ap.exit(2,safe_text(e)+'\n')


if __name__=='__main__': main()
