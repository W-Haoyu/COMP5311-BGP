import sys,unittest
sys.path.insert(0,'src')
from topology_anchor import features,standardize,select_anchors
class TopologyTests(unittest.TestCase):
 def test_dimensions_missing_and_edge_weights(self):
  f=features({('1','2'):2,('2','3'):1},'1','2')
  self.assertEqual(len(f),15);self.assertGreater(f[0],0);self.assertEqual(f[12],0.0)
  self.assertEqual(features({},'1','2'),[0.0]*15)
 def test_normalization_and_anchor_selection(self):
  x=standardize([[1,2],[3,2]]);self.assertEqual(x,[[-1.0,0.0],[1.0,0.0]])
  vs=['a','b','c'];d={(a,b):(0 if a==b else (0 if {a,b}=={'a','b'} else 2)) for a in vs for b in vs}
  chosen,_=select_anchors(vs,d,{'a':1,'b':1,'c':1})
  self.assertEqual(chosen,['a','c'])
if __name__=='__main__':unittest.main()
