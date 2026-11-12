#!/usr/bin/env python3
"""Load selected IPv4 TABLE_DUMP_V2 routes and replay contiguous updates."""
import argparse,collections,gzip,hashlib,io,ipaddress,json,struct,time
from pathlib import Path
import mrtparse
from route_state import RouteState
from update_state import apply_message

ROOT=Path(__file__).resolve().parent.parent

def scan_rib(path, prefixes, state):
    networks=[ipaddress.IPv4Network(p,strict=False) for p in prefixes]
    wanted={(net.prefixlen, net.network_address.packed[:(net.prefixlen+7)//8]) for net in networks}
    peers=None; stats=collections.Counter(); snapshot_ts=None
    with gzip.open(path,'rb') as f:
        while True:
            header=f.read(12)
            if not header: break
            if len(header)!=12: raise ValueError('truncated MRT header')
            ts,typ,sub,length=struct.unpack('!IHHI',header)
            if length>32*1024*1024: raise ValueError('unexpected MRT record length')
            body=f.read(length)
            if len(body)!=length: raise ValueError('truncated MRT body')
            stats['mrt_records']+=1
            if typ!=13 or sub not in (1,2): continue
            if sub==2:
                if len(body)<5 or body[4]>32: raise ValueError('invalid IPv4 RIB prefix')
                plen=body[4]; n=(plen+7)//8
                if len(body)<5+n: raise ValueError('truncated RIB prefix')
                if (plen,body[5:5+n]) not in wanted: continue
            obj=next(mrtparse.Reader(io.BytesIO(header+body)))
            if obj.err: stats['decode_errors']+=1;continue
            d=obj.data
            if sub==1:
                peers=d['peer_entries']; snapshot_ts=ts;stats['peer_table_records']+=1;continue
            if peers is None: raise ValueError('RIB record before PEER_INDEX_TABLE')
            prefix=f"{d['prefix']}/{d['length']}";stats['matched_rib_records']+=1
            for entry in d['rib_entries']:
                stats['matched_rib_entries']+=1
                ix=entry['peer_index']
                if ix>=len(peers): stats['bad_peer_index']+=1;continue
                attrs=entry['path_attributes']
                paths=[a.get('value',[]) for a in attrs if 2 in a.get('type',{})]
                if len(paths)!=1 or any(2 not in s.get('type',{}) for s in paths[0]) or any(17 in a.get('type',{}) for a in attrs):
                    stats['unsupported_rib_path']+=1;continue
                peer=peers[ix];vp=str(peer['peer_as'])+'@'+str(peer['peer_ip'])
                pathseq=tuple(str(a) for seg in paths[0] for a in seg.get('value',[]))
                state.announce(vp,prefix,pathseq);stats['loaded_routes']+=1
    if peers is None:raise ValueError('missing PEER_INDEX_TABLE')
    return stats,snapshot_ts

def read_updates(paths,prefixes,snapshot_ts):
    counts=collections.Counter(); events=[]; sequence=0
    for p in paths:
        per=collections.Counter()
        for obj in mrtparse.Reader(str(p)):
            if obj.err:
                per['decode_errors']+=1;obj.err=0;continue
            d=obj.data; msg=d.get('bgp_message',{})
            if 2 not in msg.get('type',{}):continue
            per['update_messages']+=1
            ts=int(next(iter(d['timestamp'])))
            if ts<snapshot_ts:per['before_snapshot']+=1;continue
            withdraw=[x for x in msg.get('withdrawn_routes',[]) if f"{x['prefix']}/{x['length']}" in prefixes]
            announce=[x for x in msg.get('nlri',[]) if f"{x['prefix']}/{x['length']}" in prefixes]
            if not withdraw and not announce:continue
            newmsg=dict(msg);newmsg['withdrawn_routes']=withdraw;newmsg['nlri']=announce
            events.append((ts,sequence,{'peer_as':d.get('peer_as'),'peer_ip':d.get('peer_ip'),'bgp_message':newmsg}));sequence+=1
            per['matched_messages']+=1
        counts[str(p.name)]=dict(per)
    events.sort(key=lambda x:(x[0],x[1]))
    return events,dict(counts)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--policy',default='results/pipeline/report.json');ap.add_argument('--rib',default='data/rrc00/bview.20230901.0000.gz');ap.add_argument('--out',default='results/rib_replay');args=ap.parse_args()
    root=ROOT;policy=json.loads((root/args.policy).read_text());prefixes=set(policy['groups'])
    state=RouteState();start=time.time();print('Scanning RIB for',len(prefixes),'prefixes',flush=True)
    rib,ts=scan_rib(root/args.rib,prefixes,state);initial_routes=len(state.routes);initial_edges=len(state.edges)
    print('RIB loaded:',initial_routes,'routes; reading updates',flush=True)
    paths=[root/'data/rrc00'/f'updates.20230901.{t}.gz' for t in ('0000','0005','0010')]
    events,counts=read_updates(paths,prefixes,ts);applied=collections.Counter(); changes=[]
    for timestamp,_,d in events:
        vp_id=str(d.get('peer_as'))+'@'+str(d.get('peer_ip'))
        before_edges=state.snapshot(vp_id)
        touched={f"{n['prefix']}/{n['length']}" for n in d['bgp_message'].get('withdrawn_routes',[])+d['bgp_message'].get('nlri',[])}
        before_routes={p:state.routes.get((vp_id,p)) for p in touched}
        # Never silently keep a stale known route when an unsupported path replaces it.
        msg=d['bgp_message'];attrs=msg.get('path_attributes',[])
        if any(17 in a.get('type',{}) for a in attrs):
            vp=str(d.get('peer_as'))+'@'+str(d.get('peer_ip'))
            for n in msg.get('nlri',[]):state.withdraw(vp,f"{n['prefix']}/{n['length']}");applied['unsupported_as4_path']+=1
            msg=dict(msg);msg['nlri']=[];d=dict(d);d['bgp_message']=msg
        applied.update(apply_message(state,d))
        after_edges=state.snapshot(vp_id)
        edge_delta=[[a,b,after_edges.get((a,b),0)-before_edges.get((a,b),0)] for a,b in sorted(before_edges.keys()|after_edges.keys()) if after_edges.get((a,b),0)!=before_edges.get((a,b),0)]
        path_delta=[{'prefix':p,'before':before_routes[p],'after':state.routes.get((vp_id,p))} for p in sorted(touched) if before_routes[p]!=state.routes.get((vp_id,p))]
        if edge_delta or path_delta:changes.append({'timestamp':timestamp,'vp':vp_id,'paths':path_delta,'edge_weight_changes':edge_delta})
    summary={'prefixes':sorted(prefixes),'rib_file':args.rib,'rib_snapshot_timestamp_utc':ts,'rib_stats':dict(rib),'initial_routes':initial_routes,'initial_directed_edges':initial_edges,'update_file_counts':counts,'applied':dict(applied),'change_events':len(changes),'final_routes':len(state.routes),'final_directed_edges':len(state.edges),'selected_update_timestamps_utc':[events[0][0],events[-1][0]] if events else None,'duration_seconds':round(time.time()-start,2),'limitations':'Restricted IPv4 prefixes; no AS_SET/AS4_PATH reconciliation, MP_REACH, or peer state resets. Unknown/unsupported paths are removed rather than treated as valid. MRT RIB snapshot consistency depends on collector dump semantics.'}
    out=root/args.out;out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'state_changes.jsonl').open('w') as f:
        for change in changes:f.write(json.dumps(change)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
