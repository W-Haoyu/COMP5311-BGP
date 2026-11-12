import gzip,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,'src')
from rib_replay import scan_rib
from route_state import RouteState

def record(st,body):return struct.pack('!IHHI',1693526400,13,st,len(body))+body
class RibReplayTests(unittest.TestCase):
 def test_selected_prefix_and_peer_mapping(self):
  peer=b'\x02'+bytes([1,1,1,1])+bytes([2,2,2,2])+struct.pack('!I',65540)
  table=bytes(4)+struct.pack('!H',0)+struct.pack('!H',1)+peer
  path=b'\x02\x01'+struct.pack('!I',65540)
  attr=b'\x40\x02'+bytes([len(path)])+path
  entry=struct.pack('!HIH',0,1693526300,len(attr))+attr
  rib=struct.pack('!I',0)+bytes([24,203,0,113])+struct.pack('!H',1)+entry
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'sample.gz'
   with gzip.open(p,'wb') as f:f.write(record(1,table)+record(2,rib))
   state=RouteState();stats,ts=scan_rib(p,{'203.0.113.0/24'},state)
   self.assertEqual(ts,1693526400);self.assertEqual(stats['loaded_routes'],1)
   self.assertEqual(state.routes[('65540@2.2.2.2','203.0.113.0/24')],('65540',))
   state2=RouteState();scan_rib(p,{'198.51.100.0/24'},state2);self.assertFalse(state2.routes)
if __name__=='__main__':unittest.main()
