"""Offline guards: shared timing, source protection and nonduplicating paid intent.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import studio
import rh


class StarterTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp=tempfile.TemporaryDirectory(prefix='portable 中文 ')
        self.root=Path(self.temp.name)
        self.project=self.root/'project'; self.project.mkdir()
        for name in ('mix.wav','vocal.wav'):
            with wave.open(str(self.project/name),'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
                w.writeframes(b'\x01\x00'*480000)
        Image.new('RGB',(864,1536),'grey').save(self.project/'ref.png')
        (self.project/'prompt.txt').write_text('The adult singer sings, with restrained expression.',encoding='utf-8')
        self.spec=dict(schema='music-video-starter-v1',mix='mix.wav',vocal='vocal.wav',vocal_alignment_reviewed=True,
            shots=[dict(id='01',start_sample=48000,end_sample=193600,image='ref.png',prompt='prompt.txt',mode='reference-audio',drive='vocal'),
                   dict(id='02',start_sample=193600,end_sample=344000,image='ref.png',prompt='prompt.txt',mode='first-frame-silent',drive='silence')])
        self.save()
    def tearDown(self): self.temp.cleanup()
    def save(self): (self.project/'project.json').write_text(json.dumps(self.spec),encoding='utf-8')
    def prepare(self):
        batch=self.root/'batch'; studio.prepare(self.project,batch); return batch
    def approval(self,job,**changes):
        p=self.root/'approval.json'
        d=dict(execution_allowed=True,max_new_tasks=1,approved_rh_coins=100,
               job_sha256=studio.sha256(job/'job.json'),instance_type='default',user_authorization_note='SIMULATED UNIT TEST ONLY')
        d.update(changes); studio.write(p,d); return p
    def test_contiguous_frames_and_immutable_sources(self):
        before={x.name:studio.sha256(x) for x in self.project.iterdir() if x.is_file()}
        batch=self.prepare(); m=studio.read(batch/'manifest.json')
        self.assertEqual(m['frames'],185)
        self.assertEqual([s['frames'] for s in m['shots']],[91,94])
        for name in ('tools/prepare_singing.py','recipes/h3-light.json','tools/studio.py'):
            self.assertEqual(m['engine']['files'][name],studio.sha256(ROOT/name))
        self.assertEqual(before,{x.name:studio.sha256(x) for x in self.project.iterdir() if x.is_file()})
    def test_silent_drive_does_not_silence_mix(self):
        j=self.prepare()/'jobs/02'
        with wave.open(str(j/'drive.wav'),'rb') as w: self.assertFalse(any(w.readframes(w.getnframes())))
        with wave.open(str(j/'mix.wav'),'rb') as w: self.assertTrue(any(w.readframes(w.getnframes())))
        self.assertEqual(studio.inspect_graph(studio.read(j/'workflow.api.json'),'delivery')['mode'],'first-frame-silent')
    def test_reject_gap(self):
        self.spec['shots'][1]['start_sample']+=1600; self.save()
        with self.assertRaisesRegex(ValueError,'continuous'): studio.validate(self.project)
    def test_reject_overlap(self):
        self.spec['shots'][1]['start_sample']-=1600; self.save()
        with self.assertRaisesRegex(ValueError,'continuous'): studio.validate(self.project)
    def test_reject_off_grid_cut(self):
        self.spec['shots'][0]['start_sample']+=1; self.save()
        with self.assertRaisesRegex(ValueError,'30 fps'): studio.validate(self.project)
    def test_reject_unreviewed_alignment(self):
        self.spec['vocal_alignment_reviewed']=False; self.save()
        with self.assertRaisesRegex(ValueError,'alignment'): studio.validate(self.project)
    def test_reject_silent_mode_with_vocal(self):
        self.spec['shots'][1]['drive']='vocal'; self.save()
        with self.assertRaisesRegex(ValueError,'Silent shots'): studio.validate(self.project)
    def test_reject_small_reference(self):
        from PIL import Image
        Image.new('RGB',(576,1024)).save(self.project/'ref.png')
        with self.assertRaisesRegex(ValueError,'reference'): studio.validate(self.project)
    def test_path_does_not_escape_project(self):
        with self.assertRaises(ValueError): studio.local(self.project,'../private.txt')
    def test_srt_rejects_zero_duration(self):
        with self.assertRaises(ValueError): studio.srt_cues('1\n00:00:01,000 --> 00:00:01,000\nword')
    def test_srt_text_cannot_inject_ass_override(self):
        self.assertEqual(studio.clean_ass('{\\pos(1,2)}\ntext'),'｛＼pos(1,2)｝\\Ntext')
    def test_existing_batch_is_not_overwritten(self):
        self.prepare()
        with self.assertRaises(FileExistsError): studio.prepare(self.project,self.root/'batch')
    def test_frozen_job_rejects_mutation(self):
        j=self.prepare()/'jobs/01'; (j/'prompt.txt').write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Frozen input'): rh.check_job(j)
    def test_zero_budget_blocks_network(self):
        j=self.prepare()/'jobs/01'; a=self.approval(j,approved_rh_coins=0)
        with patch.object(rh,'Client') as client:
            with self.assertRaises(ValueError): rh.submit(j,a,'123',client)
            client.assert_not_called()
    def test_approval_is_bound_to_exact_job(self):
        j=self.prepare()/'jobs/01'; a=self.approval(j,job_sha256='wrong')
        with self.assertRaisesRegex(ValueError,'exact job'): rh.authorization(j,a)
    def test_success_saves_task_before_followup_and_blocks_duplicate(self):
        class Fake:
            key='test-key-never-real'
            def upload(self,p): return 'input/'+p.name
            def post(self,endpoint,body):
                assert json.loads(body['workflow'])['9']['inputs']['image'].startswith('input/')
                return {'code':0,'data':{'taskId':'12345','taskStatus':'QUEUED'}}
        j=self.prepare()/'jobs/01'; a=self.approval(j)
        r=rh.submit(j,a,'123',Fake)
        self.assertEqual(r['task_id'],'12345')
        self.assertNotIn(Fake.key,(j/'rh-state.json').read_text('utf-8'))
        with self.assertRaisesRegex(ValueError,'record exists'): rh.submit(j,a,'123',Fake)
    def test_timeout_persists_uncertainty_and_recovers_without_resubmit(self):
        class Fake:
            key='test'
            def upload(self,p): return 'input/'+p.name
            def post(self,*args): raise TimeoutError('connection uncertain')
        j=self.prepare()/'jobs/01'; a=self.approval(j)
        with self.assertRaises(TimeoutError): rh.submit(j,a,'123',Fake)
        self.assertEqual(studio.read(j/'rh-state.json')['status'],'SUBMIT_UNCERTAIN')
        r=rh.recover(j,'45678'); self.assertEqual(r['task_id'],'45678')
        with self.assertRaises(ValueError): rh.recover(j,'99999')


if __name__=='__main__': unittest.main()
