import sys,unittest
sys.path.insert(0,'src')
from route_state import RouteState
class RoutingTest(unittest.TestCase):
 def test_replace_withdraw_shared(self):
  s=RouteState();s.announce('v','p',[1,1,2,3]);s.announce('v','q',[1,2,4])
  self.assertEqual(s.edges[(1,2)],2)
  self.assertEqual(s.announce('v','p',[1,5,3]),(1,1,2,3))
  self.assertEqual(s.edges[(1,2)],1);self.assertNotIn((2,3),s.edges)
  s.withdraw('v','q');self.assertNotIn((1,2),s.edges)
  self.assertIsNone(s.withdraw('v','missing'))
if __name__=='__main__':unittest.main()

class PeerGraphTests(unittest.TestCase):
 def test_shared_edges_are_independent(self):
  s=RouteState();s.announce('a','p',['1','2']);s.announce('b','p',['1','2'])
  self.assertEqual(s.snapshot('a'),{('1','2'):1});self.assertEqual(s.snapshot('b'),{('1','2'):1})
  self.assertEqual(s.snapshot()[('1','2')],2)
  s.withdraw('a','p');self.assertEqual(s.snapshot('a'),{});self.assertEqual(s.snapshot('b'),{('1','2'):1})
