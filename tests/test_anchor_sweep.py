import sys,unittest
from collections import defaultdict
sys.path.insert(0,'src')
from anchor_sweep import measure
class AnchorSweepTests(unittest.TestCase):
 def test_budget_and_anchor_precedence(self):
  a=('p',1,('a',('1','2'),()));b=('p',2,('b',('2','3'),()))
  ev=[a,b];vpmap={'a':[a],'b':[b]};vplinks={'a':{('1','2')},'b':{('2','3')}}
  rules={'p':{'drop_vps':['a','b']}}
  x=measure((ev,vpmap,vplinks,{('1','2'),('2','3')},{}),rules,{'a'},repeats=10)
  self.assertEqual(x['kept'],1);self.assertEqual(x['coverage'],.5)
  self.assertLessEqual(x['random_vp_retained'],x['retained'])
if __name__=='__main__':unittest.main()
