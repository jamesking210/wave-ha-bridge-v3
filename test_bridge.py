import unittest
from pathlib import Path
import tempfile,json
from bridge import Delivery,input_mute,snapshot_mute,port_from_file,validate_config
from configure import candidates
C={'device_id':'mic','input_id':'in'}
class Tests(unittest.TestCase):
 def test_strict_identity_and_boolean(self):
  for d in [{'id':'other','inputs':[{'id':'in','isMuted':True}]},{'id':'mic','inputs':[{'id':'other','isMuted':True}]},{'id':'mic','inputs':[{'id':'in','isMuted':'false'}]}]: self.assertIsNone(input_mute(d,C))
  self.assertIs(input_mute({'id':'mic','inputs':[{'id':'in','isMuted':False}]},C),False)
 def test_missing_device_unknown(self):
  self.assertIsNone(snapshot_mute({'inputDevices':[]},C))
 def test_dry_run_never_sends(self):
  d=Delivery(C,False,lambda *_:self.fail('sent')); d.observe(True); d.tick(0)
 def test_dedup_and_reconnect(self):
  calls=[]; d=Delivery(C,True,lambda c,v:calls.append(v))
  for v in [True,True,None,True,False,False]: d.observe(v); d.tick(0)
  self.assertEqual(calls,[True,False])
 def test_retry_latest_not_stale(self):
  calls=[]
  def send(c,v):
   calls.append(v)
   if len(calls)==1: raise OSError()
  d=Delivery(C,True,send); d.observe(True); d.tick(0); d.tick(1)
  d.observe(False); d.tick(2); d.tick(6)
  self.assertEqual(calls,[True,False])
 def test_disconnect_cancels_retry(self):
  calls=[]
  def send(c,v): calls.append(v); raise OSError()
  d=Delivery(C,True,send); d.observe(True); d.tick(0); d.observe(None); d.tick(10)
  self.assertEqual(calls,[True])
 def test_port_rediscovery_validation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'port.json'
   for port in [53498,12345]:
    p.write_text(json.dumps({'port':port})); self.assertEqual(port_from_file(p),port)
   for port in [True,0,65536,'53498']:
    p.write_text(json.dumps({'port':port}))
    with self.assertRaises(ValueError): port_from_file(p)
class SetupTests(unittest.TestCase):
 def config(self):
  return dict(device_id='device',input_id='input',ha_base='http://homeassistant.local:8123',muted_webhook='abc-123',unmuted_webhook='def_456',semantics_verified=False)
 def test_valid_config(self):
  validate_config(self.config())
 def test_reject_unsafe_base_and_ids(self):
  for key,value in [('ha_base','ftp://host'),('ha_base','http://user:secret@host'),('ha_base','http://host/api/webhook/test'),('muted_webhook','abc/def'),('semantics_verified','true'),('input_id','')]:
   with self.subTest(key=key,value=value):
    c=self.config(); c[key]=value
    with self.assertRaises(ValueError): validate_config(c)
 def test_distinct_webhooks(self):
  c=self.config(); c['unmuted_webhook']=c['muted_webhook']
  with self.assertRaises(ValueError): validate_config(c)
 def test_discovery_requires_boolean_and_ids(self):
  devices=[{'id':'device','inputs':[{'id':'a','isMuted':False},{'id':'b','isMuted':'false'},{'isMuted':True}]}]
  self.assertEqual(len(candidates(devices)),1)
  self.assertEqual(candidates(devices)[0][1]['id'],'a')
if __name__=='__main__': unittest.main()

