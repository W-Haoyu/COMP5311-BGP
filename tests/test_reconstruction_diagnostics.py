import sys,unittest
sys.path.insert(0,'src')
from reconstruction_diagnostics import confidence_model,predict
class DiagnosticTests(unittest.TestCase):
 def test_ambiguous_suppressed_and_unseen_retained(self):
  a=('a',('1',),());b=('b',('2',),());c=('c',('3',),());z=('z',('9',),())
  m=confidence_model([(0,a),(1,b),(300,a),(301,c)])
  self.assertEqual(m[a][1],.5)
  out,s=predict([(500,a),(501,z)],set(),m,.7)
  self.assertEqual(out,{(500,a),(501,z)});self.assertEqual(s['unseen_signature'],1)
  out,s=predict([(500,a)],set(),m,.5)
  self.assertGreater(len(out),1)
if __name__=='__main__':unittest.main()
