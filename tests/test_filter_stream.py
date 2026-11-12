import json,subprocess,sys,tempfile,unittest
from pathlib import Path
class StreamTest(unittest.TestCase):
 def test_filter_and_bad_record(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.json';p.write_text(json.dumps({'anchors':['a'],'drop_pairs':[['a','p'],['b','p']]}))
   inp='\n'.join(json.dumps(x) for x in [{'vp':'a','prefix':'p'},{'vp':'b','prefix':'p'},{'vp':'b','prefix':'q'}])+'\n'
   r=subprocess.run([sys.executable,'src/filter_stream.py','--policy',str(p)],input=inp,text=True,capture_output=True)
   self.assertEqual(r.returncode,0);self.assertEqual([json.loads(x)['prefix'] for x in r.stdout.splitlines()],['p','q'])
   r=subprocess.run([sys.executable,'src/filter_stream.py','--policy',str(p)],input='{}\n',text=True,capture_output=True)
   self.assertEqual(r.returncode,2)
if __name__=='__main__':unittest.main()
