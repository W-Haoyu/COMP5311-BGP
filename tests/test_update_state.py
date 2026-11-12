import sys,unittest
sys.path.insert(0,'src')
from update_state import RouteState,apply_message
class UpdateTests(unittest.TestCase):
 def test_announcements_withdrawals(self):
  s=RouteState();d={'peer_as':'1','peer_ip':'a','bgp_message':{'type':{2:'UPDATE'},'nlri':[{'prefix':'1.2.3.0','length':24}],'path_attributes':[{'type':{2:'AS_PATH'},'value':[{'type':{2:'AS_SEQUENCE'},'value':['1','2']}]}]}}
  self.assertEqual(apply_message(s,d)['announced'],1);self.assertIn(('1','2'),s.snapshot('1@a'))
  d['bgp_message']={'type':{2:'UPDATE'},'withdrawn_routes':[{'prefix':'1.2.3.0','length':24}]}
  self.assertEqual(apply_message(s,d)['withdrawn'],1);self.assertEqual(s.snapshot(),{})
if __name__=='__main__':unittest.main()

class UnsupportedTests(unittest.TestCase):
 def test_unknown_replacement_removes_stale_route(self):
  s=RouteState();s.announce('1@a','1.2.3.0/24',['1','2'])
  d={'peer_as':'1','peer_ip':'a','bgp_message':{'type':{2:'UPDATE'},'nlri':[{'prefix':'1.2.3.0','length':24}],'path_attributes':[{'type':{2:'AS_PATH'},'value':[{'type':{1:'AS_SET'},'value':['3']}]}]}}
  result=apply_message(s,d)
  self.assertEqual(result['unsupported'],1);self.assertEqual(s.snapshot(),{})
