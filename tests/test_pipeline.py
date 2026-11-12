import sys,unittest
sys.path.insert(0,'src')
from pipeline import cross_prefix,apply_policy,choose_anchors
class PolicyTests(unittest.TestCase):
 def test_priority(self):
  self.assertTrue(apply_policy('v','p',{'v'},{('v','p')}))
  self.assertFalse(apply_policy('v','p',set(),{('v','p')}))
  self.assertTrue(apply_policy('v','q',set(),{('v','p')}))
 def test_time_and_multiplicity(self):
  def e(ts): return (ts,('1','2'),())
  self.assertEqual(cross_prefix({('v','p'):[e(0)],('v','q'):[e(100)]}),{('v','q')})
  self.assertEqual(cross_prefix({('v','p'):[e(0)],('v','q'):[e(101)]}),set())
  self.assertEqual(cross_prefix({('v','p'):[e(0)],('v','q'):[e(0),e(1)]}),set())
 def test_identical_anchor_features(self):
  self.assertEqual(choose_anchors(['a','b'],{'a':{1},'b':{1}},{'a':1,'b':1}),['a'])
if __name__=='__main__': unittest.main()
