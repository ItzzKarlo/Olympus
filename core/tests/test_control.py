import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import CoreSettings, PersistenceSettings, BackupSettings
from olympus_core.control.auth import password_record, ControlError
from olympus_core.control.config_api import checksum
from olympus_core.control.overrides import OverrideStore, OverrideRequest, Simulation
from olympus_core.control.redact import redact
from olympus_core.control.routes import Control, install_control
from olympus_core.control.services import Services
from olympus_core.control.storage import atomic_write
from olympus_core.display.hub import DisplayHub
from olympus_core.persistence.database import Database
from olympus_core.persistence.devices import DeviceRepository
from olympus_core.persistence.enrollment import EnrollmentRepository
from olympus_core.services.state import StateService

ROOT=Path(__file__).resolve().parents[2]
PASSWORD='a long testing password 123!'


class ControlTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.credentials=self.root/'credentials.json';atomic_write(self.credentials,json.dumps(password_record(PASSWORD)))
        self.config=self.root/'config.toml';self.original='[security]\nrequire_agent_auth=true\n[night]\nenabled=true\nweekday_start="22:00"\n';self.config.write_text(self.original)
        settings=replace(CoreSettings(),persistence=PersistenceSettings(database_path=self.root/'core.db'),backup=BackupSettings(directory=self.root/'backups'))
        self.db=Database(settings.persistence.resolved_database_path);self.db.initialize();self.addCleanup(self.db.close)
        self.devices=DeviceRepository(self.db);self.enrollment=EnrollmentRepository(self.db);self.states=StateService(AgentRegistry());self.published=[];self.commands=[]
        async def publish(): self.published.append(self.states.display_state())
        def run(args,**kw):
            self.commands.append(args)
            text='Id=olympus-core.service\nActiveState=active\nSubState=running\n' if 'show' in args else json.dumps({'MESSAGE':'safe log','PRIORITY':'6'})+'\n' if args[0].endswith('journalctl') else ''
            return subprocess.CompletedProcess(args,0,text,'')
        self.control=Control(settings,self.states,DisplayHub(),self.devices,self.enrollment,publish,runtime=self.root/'runtime',credentials=self.credentials,config=self.config,history=self.root/'history',services=Services(run))
        self.app=FastAPI();install_control(self.app,self.control);self.client=TestClient(self.app);self.addCleanup(self.client.close)

    def login(self):
        r=self.client.post('/api/control/login',json={'password':PASSWORD},headers={'Origin':'http://testserver'})
        self.assertEqual(r.status_code,200,r.text);self.client.headers.update({'X-CSRF-Token':r.json()['data']['csrf'],'Origin':'http://testserver'});return r

    def test_anonymous_and_static(self):
        self.assertEqual(self.client.get('/api/control/status').status_code,401)
        self.assertEqual(self.client.get('/control/',follow_redirects=False).status_code,307)
        r=self.client.get('/control/login');self.assertEqual(r.status_code,200);self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
        self.assertEqual(self.client.get('/control/static/secrets.env').status_code,404)

    def test_login_rate_limit_and_origin(self):
        self.assertEqual(self.client.post('/api/control/login',json={'password':PASSWORD}).status_code,403)
        for i in range(6):
            r=self.client.post('/api/control/login',json={'password':'incorrect'},headers={'Origin':'http://testserver'})
            self.assertEqual(r.status_code,401 if i<5 else 429)

    def test_sessions_csrf_expiry_logout_rotation(self):
        r=self.login();self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=strict',r.headers['set-cookie'])
        old=self.client.cookies.get('olympus_control');self.login();self.assertNotEqual(old,self.client.cookies.get('olympus_control'))
        self.assertEqual(self.client.get('/api/control/status').status_code,200)
        for headers in [{'X-CSRF-Token':''},{'Origin':'http://evil.test'}]:
            self.assertEqual(self.client.put('/api/control/overrides',json={'scene':'idle'},headers=headers).status_code,403)
        self.assertEqual(self.client.post('/api/control/logout').status_code,200);self.assertEqual(self.client.get('/api/control/status').status_code,401)
        self.login();self.control.auth.clock=lambda:time.time()+30000
        self.assertEqual(self.client.get('/api/control/status').status_code,401)

    def test_password_rotation_and_missing_credentials(self):
        self.login();atomic_write(self.credentials,json.dumps(password_record(PASSWORD)))
        self.assertEqual(self.client.get('/api/control/status').status_code,401)
        self.credentials.unlink();self.assertEqual(self.client.post('/api/control/login',json={'password':PASSWORD}).status_code,503)

    def test_invalid_schema_hides_input(self):
        self.login()
        for body in [{'scene':'private-value'},{'seasonal_date':'2026-02-31'},{'ttl_minutes':999},{'simulation':{'kind':'system','variant':'rm -rf /'}}]:
            r=self.client.put('/api/control/overrides',json=body);self.assertEqual(r.status_code,422,r.text);self.assertFalse(r.json()['ok']);self.assertNotIn('private-value',r.text)

    def test_missing_empty_broken_override(self):
        real=self.states.current();self.assertEqual(self.control.overrides.apply(real),real)
        self.control.overrides.write(OverrideRequest());self.assertIsNone(self.control.overrides.read())
        self.control.overrides.path.parent.mkdir(exist_ok=True)
        for text in ['{bad','{}','{"settings":{"scene":"shell"}}']:
            self.control.overrides.path.write_text(text);self.assertIsNone(self.control.overrides.read());self.assertEqual(self.control.overrides.apply(real),real)

    def test_date_real_state_and_reset(self):
        self.login();self.assertEqual(self.client.put('/api/control/overrides',json={'seasonal_date':'2026-12-24'}).status_code,200)
        shown=self.published[-1];self.assertEqual(shown.control['seasonal_date'],'2026-12-24');self.assertLess(abs(shown.generated_at.timestamp()-time.time()),5);self.assertIsNone(self.states.current().control)
        self.assertEqual(self.client.delete('/api/control/overrides').status_code,200);self.assertIsNone(self.published[-1].control)

    def test_ttl_and_restart(self):
        clock=[1000.];store=OverrideStore(self.root/'override.json',clock=lambda:clock[0]);store.write(OverrideRequest(scene='idle',ttl_minutes=15))
        self.assertIsNotNone(OverrideStore(store.path,clock=lambda:1001).read());clock[0]=1901;self.assertIsNone(store.read());self.assertFalse(store.path.exists())
        store.write(OverrideRequest(scene='night',ttl_minutes=0));clock[0]=99999;self.assertIsNotNone(store.read())

    def test_day_night_and_all_forced_scenes(self):
        for mode in ['day','night']:
            self.control.overrides.write(OverrideRequest(day_night=mode));self.assertEqual(self.states.display_state().time_policy.is_night,mode=='night')
        for scene in ['idle','night','media','development','gaming','matchday','news']:
            self.control.overrides.write(OverrideRequest(scene=scene));shown=self.states.display_state();self.assertIsNotNone(shown.control);self.assertEqual(shown.mode.value,scene)

    def test_all_simulations_preserve_real(self):
        variants={'news':['notable','important','major','critical'],'system':['blocker','warning','critical','dns-degraded','dns-down','gateway-down','internet-down','service-down','agent-offline'],'football':['pre-match','kickoff','live','bayern-goal','opponent-goal','halftime','second-half','full-time','victory','defeat','draw'],'media':['playing','paused'],'gaming':['fortnite','minecraft','among-us','goat-simulator','custom'],'development':['active']}
        real=self.states.current().model_dump()
        for kind,options in variants.items():
            for variant in options:
                with self.subTest(kind=kind,variant=variant):
                    self.control.overrides.write(OverrideRequest(simulation=Simulation(kind=kind,variant=variant)))
                    self.assertIsNotNone(self.states.display_state().control);self.assertEqual(self.states.current().model_dump(),real)

    def test_real_critical_retained(self):
        from olympus_core.models.monitoring import ActiveAlert
        from datetime import datetime,timezone
        alert=ActiveAlert(id='real',incident_key='real',type='real.down',severity='critical',title='Real',message='real',source='network',started_at=datetime.now(timezone.utc))
        self.states._events.active_alerts=lambda:[alert]
        self.control.overrides.write(OverrideRequest(scene='media',simulation=Simulation(kind='system',variant='critical')))
        shown=self.states.display_state();self.assertEqual(shown.alerts[0].id,'real');self.assertEqual(len(shown.alerts),2)

    def test_service_allowlist_confirmation_and_failure(self):
        self.login()
        for service,action in [('sshd','restart'),('core','kill'),('backup','reset-failed'),('core;reboot','restart')]:
            self.assertEqual(self.client.post(f'/api/control/services/{service}/{action}',json={'confirm':True}).status_code,403)
        self.assertEqual(self.commands,[])
        self.assertEqual(self.client.post('/api/control/services/kiosk/restart',json={'confirm':False}).status_code,400)
        self.assertEqual(self.client.post('/api/control/services/kiosk/restart',json={'confirm':True}).status_code,200)
        self.assertEqual(self.commands[-1][-2:],['restart','olympus-kiosk.service'])
        self.control.services.run=lambda *a,**kw:subprocess.CompletedProcess(a,1,'','Access denied')
        self.assertEqual(self.client.post('/api/control/services/kiosk/restart',json={'confirm':True}).status_code,502)

    def test_core_restart_background(self):
        self.login();r=self.client.post('/api/control/services/core/restart',json={'confirm':True});self.assertEqual(r.status_code,202);self.assertTrue(r.json()['data']['scheduled']);self.assertEqual(self.commands[-1][-2:],['restart','olympus-core.service'])

    def test_logs_and_redaction(self):
        self.login();self.assertEqual(self.client.get('/api/control/logs?unit=sshd').status_code,403);self.assertEqual(self.client.get('/api/control/logs?count=99999').status_code,403);self.assertEqual(self.client.get('/api/control/logs?unit=kiosk').status_code,200)
        with patch.dict(os.environ,{'OLYMPUS_SECRET':'supersecret'}):
            text=redact('supersecret Bearer abc123 token=hidden OLYMPUS-abcdefghijklmnopqrstuvwxyz')
            for secret in ['supersecret','abc123','token=hidden','OLYMPUS-abc']:self.assertNotIn(secret,text)

    def test_config_atomic_backup_conflict(self):
        self.login();text=self.original.replace('22:00','21:30');body={'text':text,'checksum':checksum(self.original)}
        r=self.client.post('/api/control/config/validate',json=body);self.assertEqual(r.status_code,200,r.text);self.assertIn('21:30',r.json()['data']['diff']);self.assertEqual(self.config.read_text(),self.original)
        self.assertEqual(self.client.post('/api/control/config/apply',json={**body,'confirm':True}).status_code,200)
        history=list((self.root/'history').glob('*.toml'));self.assertEqual(len(history),1);self.assertEqual(history[0].read_text(),self.original);self.assertEqual(self.config.read_text(),text)
        self.assertEqual(self.client.post('/api/control/config/apply',json={**body,'confirm':True}).status_code,409)

    def test_config_invalid_locked_and_structure(self):
        self.login()
        for text in ['[broken','[security]\nrequire_agent_auth=false','[night]\nweekday_start="27:91"']:
            r=self.client.post('/api/control/config/apply',json={'text':text,'checksum':checksum(self.original),'confirm':True});self.assertEqual(r.status_code,400,r.text);self.assertEqual(self.config.read_text(),self.original)
        draft=self.control.config.patch(self.original+'\n[custom]\nunknown="keep me"\n',{'night.weekday_start':'21:00'});self.assertIn('unknown="keep me"',draft)
        self.config.write_text('password="must-never-be-exposed"\n');r=self.client.get('/api/control/config');self.assertNotIn('must-never-be-exposed',r.text);self.assertFalse(r.json()['data']['editable'])

    def test_history_validation_traversal_symlinks(self):
        with self.assertRaises(ControlError):self.control.config.historical('../secrets.env')
        self.root.joinpath('history').mkdir();name='20260915T120000-12345678.toml';self.root.joinpath('history',name).write_text('[broken')
        self.login();self.assertEqual(self.client.post('/api/control/config/restore',json={'name':name,'checksum':checksum(self.original),'confirm':True}).status_code,400);self.assertEqual(self.config.read_text(),self.original)
        linked=self.root/'linked';linked.symlink_to(self.config)
        with self.assertRaises(ValueError):atomic_write(linked,'bad')
        self.control.overrides.path.symlink_to(self.config);self.assertIsNone(self.control.overrides.read())

    def test_devices_enrollment_revocation(self):
        self.login();r=self.client.post('/api/control/enrollment',json={'label':'Zeus','ttl_minutes':10});token=r.json()['data']['token']
        self.enrollment.enroll(token=token,agent_id='agent',display_name='<script>alert(1)</script>',platform='linux',public_key=b'a'*32)
        self.assertEqual(len(self.client.get('/api/control/devices').json()['data']),1)
        self.assertEqual(self.client.post('/api/control/devices/agent/revoke',json={'confirm':True}).status_code,200);self.assertTrue(self.devices.get('agent').revoked)

    def test_backups_release_diagnostics(self):
        self.login();self.assertEqual(self.client.post('/api/control/backups').status_code,200);self.assertEqual(self.client.get('/api/control/backups').json()['data']['count'],1)
        self.assertEqual(self.client.get('/api/control/releases').json()['data']['version'],(ROOT/'VERSION').read_text().strip())
        r=self.client.get('/api/control/diagnostics');self.assertEqual(r.status_code,200);self.assertNotIn(PASSWORD,r.text)

    def test_integration_failure_simulations_reset_to_real_state(self):
        self.login()
        real_before = self.control.state_service.current().model_dump()
        for kind, variant in (("media", "outage"), ("media", "local"), ("news", "recovery"), ("football", "score-correction"), ("football", "outage")):
            from olympus_core.control.overrides import OverrideDocument, OverrideRequest
            from olympus_core.control.simulation import present
            import time
            doc = OverrideDocument(settings=OverrideRequest(simulation={"kind": kind, "variant": variant}), created_at=time.time(), expires_at=None)
            state = present(self.control.state_service.current(), doc)
            self.assertTrue(state.control["active"])
        self.assertEqual(self.control.state_service.current().mode.value, real_before["mode"])

    def test_frontend_no_unsafe_html(self):
        for js in (ROOT/'core/olympus_core/control/static').glob('*.js'):
            self.assertNotIn('innerHTML',js.read_text());self.assertNotIn('eval(',js.read_text())


if __name__=='__main__':unittest.main()
