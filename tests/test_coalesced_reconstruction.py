import sys,unittest
sys.path.insert(0,'src')
from coalesced_reconstruction import index_predictions
class CoalescingTest(unittest.TestCase):
 def test_preserve_direct_observations_and_suppress_inferences(self):
  a=('a',('1',),());b=('b',('2',),());g=frozenset([a,b])
  output=index_predictions([(0,a),(10,a),(110,a)],{a:g})['a']
  self.assertTrue({(0,a),(10,a),(110,a)} <= output)
  self.assertIn((0,b),output);self.assertNotIn((10,b),output);self.assertIn((110,b),output)
if __name__=='__main__':unittest.main()
