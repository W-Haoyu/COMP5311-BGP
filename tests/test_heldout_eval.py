import sys,unittest
sys.path.insert(0,'src')
from heldout_eval import links,stats
class HeldoutTests(unittest.TestCase):
 def test_deduplicate_prepends_and_undirected(self):
  self.assertEqual(links(('3','3','2','1','2')),{('2','3'),('1','2')})
 def test_reference_and_counts(self):
  a=('p',1,('v',('1','2','3'),()))
  b=('q',2,('v',('3','2'),()))
  r=stats([a,b],2)
  self.assertEqual(r['records'],2);self.assertEqual(r['link_recall'],1)
  self.assertEqual(r['prefix_path_pairs'],2);self.assertEqual(r['vps'],1)
if __name__=='__main__':unittest.main()
