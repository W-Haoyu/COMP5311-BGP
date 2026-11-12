import gzip,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,'src')
from fast_selected import read_selected_fast
class FastTest(unittest.TestCase):
 def test_prefilter_skips_unrelated_records(self):
  body=b'irrelevant';h=struct.pack('!IHHI',1,16,4,len(body))
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.gz'
   with gzip.open(p,'wb') as f:f.write(h+body)
   events,counts=read_selected_fast(p,{'203.0.113.0/24'})
   self.assertFalse(events);self.assertEqual(counts['mrt_records'],1)
if __name__=='__main__':unittest.main()
