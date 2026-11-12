"""Conservative raw-MRT prefilter for ordinary IPv4 NLRI, followed by mrtparse."""
import collections,gzip,io,ipaddress,struct
import mrtparse

def read_selected_fast(path,wanted):
    tokens=[]
    for p in wanted:
        net=ipaddress.IPv4Network(p,strict=False);n=(net.prefixlen+7)//8
        tokens.append(bytes([net.prefixlen])+net.network_address.packed[:n])
    events=collections.defaultdict(list);counts=collections.Counter()
    with gzip.open(path,'rb') as f:
        while True:
            h=f.read(12)
            if not h:break
            if len(h)!=12:raise ValueError('truncated MRT header')
            ts,typ,sub,length=struct.unpack('!IHHI',h)
            if length>32*1024*1024:raise ValueError('MRT record unexpectedly large')
            body=f.read(length)
            if len(body)!=length:raise ValueError('truncated MRT record')
            counts['mrt_records']+=1
            if typ not in (16,17) or not any(token in body for token in tokens):continue
            counts['candidate_records']+=1
            try: obj=next(mrtparse.Reader(io.BytesIO(h+body)))
            except Exception as e:raise RuntimeError(f'MRT framing error: {e}') from e
            if obj.err:counts['candidate_decode_errors']+=1;continue
            d=obj.data;msg=d.get('bgp_message',{})
            if 2 not in msg.get('type',{}):continue
            prefixes=[f"{n['prefix']}/{n['length']}" for n in msg.get('nlri',[]) if f"{n['prefix']}/{n['length']}" in wanted]
            if not prefixes:continue
            attrs=msg.get('path_attributes',[]);paths=[a.get('value',[]) for a in attrs if 2 in a.get('type',{})]
            if len(paths)!=1 or any(2 not in s.get('type',{}) for s in paths[0]):counts['excluded_paths']+=len(prefixes);continue
            seq=tuple(str(v) for seg in paths[0] for v in seg.get('value',[]));com=[]
            for a in attrs:
                t=next(iter(a.get('type',{})),None)
                if t in (8,32):com.extend((t,str(v)) for v in a.get('value',[]))
            sig=(str(d.get('peer_as'))+'@'+str(d.get('peer_ip')),seq,tuple(sorted(com)))
            timestamp=int(next(iter(d['timestamp'])))
            for p in prefixes:events[p].append((timestamp,sig));counts['selected_prefix_announcements']+=1
    return events,dict(counts)
