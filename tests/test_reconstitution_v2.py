import sys,unittest
sys.path.insert(0,'src')
from reconstitution_v2 import match_count,index_predictions,select_vps
class ReconstructionTests(unittest.TestCase):
 def test_slack_and_one_to_one(self):
  a=('a',('1',),());b=('b',('2',),())
  self.assertEqual(match_count([(0,a),(10,a),(0,b)],{(100,a),(100,b)}),2)
  self.assertEqual(match_count([(0,a)],{(101,a)}),0)
 def test_prediction_and_selection(self):
  a=('a',('1',),());b=('b',('2',),());g=frozenset([a,b])
  obs=[(0,a),(10,b),(200,a),(210,b)];lookup={a:g,b:g}
  pred=index_predictions(obs,lookup)
  self.assertEqual(match_count(obs,pred['a']),4)
  selected,ps=select_vps(obs,lookup)
  self.assertEqual(selected,['a']);self.assertEqual(match_count(obs,ps),4)
if __name__=='__main__':unittest.main()
