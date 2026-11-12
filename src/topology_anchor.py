#!/usr/bin/env python3
"""Small graph-event anchor experiment. It is not the full paper algorithm."""
import argparse,collections,copy,json,math,statistics,time
from pathlib import Path
import networkx as nx
from rib_replay import scan_rib
from route_state import RouteState
ROOT=Path(__file__).resolve().parent.parent

def graph(edgecounts):
    g=nx.Graph()
    for (a,b),w in edgecounts.items():
        if a==b or w<=0:continue
        old=g.get_edge_data(a,b,{}).get('weight',0)
        g.add_edge(a,b,weight=old+w)
    for a,b,d in g.edges(data=True):d['distance']=1.0/d['weight']
    return g

def node_features(g,n):
    if n not in g:return [0.0]*6
    lengths=nx.single_source_dijkstra_path_length(g,n,weight='distance')
    ds=[v for k,v in lengths.items() if k!=n and v>0]
    closeness=(len(ds)/sum(ds) if ds else 0.0)
    if len(g)>1:closeness*=len(ds)/(len(g)-1)
    harmonic=sum(1/x for x in ds)
    avg=nx.average_neighbor_degree(g,nodes=[n],weight='weight')[n]
    eccentric=max(ds,default=0.0)
    triangles=nx.triangles(g,n)
    clustering=nx.clustering(g,n,weight='weight')
    return [closeness,harmonic,avg,eccentric,float(triangles),clustering]

def features(edgecounts,a,b):
    g=graph(edgecounts);x=node_features(g,a);y=node_features(g,b)
    nodes=[n for n in (a,b) if n in g]
    if len(nodes)<2 or a==b:return [v for pair in zip(x,y) for v in pair]+[0.0]*3
    pair=[(a,b)]
    j=next(nx.jaccard_coefficient(g,pair))[2]
    aa=next(nx.adamic_adar_index(g,pair))[2]
    pa=next(nx.preferential_attachment(g,pair))[2]
    return [v for pair in zip(x,y) for v in pair]+[j,aa,pa]

def standardize(matrix):
    if not matrix:return []
    cols=list(zip(*matrix)); means=[statistics.fmean(c) for c in cols];stds=[statistics.pstdev(c) for c in cols]
    return [[(x-m)/s if s>1e-12 else 0.0 for x,m,s in zip(row,means,stds)] for row in matrix]

def select_anchors(vps,dist,volumes,gamma=.1):
    if not vps:return [],{}
    values=[dist[a,b] for i,a in enumerate(vps) for b in vps[i+1:]]
    lo=min(values,default=0);hi=max(values,default=0)
    def red(a,b):
        if a==b:return 1.0
        return 1.0-(dist[a,b]-lo)/(hi-lo) if hi-lo>1e-12 else 1.0
    chosen=[min(vps,key=lambda a:(sum(dist[a,b] for b in vps),a))]
    while len(chosen)<len(vps):
        remain=[v for v in vps if v not in chosen]; maxred={v:max(red(v,c) for c in chosen) for v in remain}
        if all(maxred[v]>=1-1e-12 for v in remain):break
        k=max(1,math.ceil(gamma*len(remain)))
        candidates=sorted(remain,key=lambda v:(maxred[v],v))[:k]
        chosen.append(min(candidates,key=lambda v:(volumes.get(v,0),v)))
    return chosen,{'distance_min':lo,'distance_max':hi,'gamma':gamma}

def main():
    p=argparse.ArgumentParser();p.add_argument('--max-events',type=int,default=6);p.add_argument('--window',type=int,default=100);args=p.parse_args()
    start=time.time();policy=json.loads((ROOT/'results/pipeline/report.json').read_text());prefixes=set(policy['groups'])
    state=RouteState();print('Loading initial RIB...',flush=True)
    rib,ts=scan_rib(ROOT/'data/rrc00/bview.20230901.0000.gz',prefixes,state)
    initial={vp:state.snapshot(vp) for vp,_ in state.routes}; print('Loading recorded state changes...',flush=True)
    changes=[]
    with (ROOT/'results/rib_replay/state_changes.jsonl').open() as f:
        for line in f:changes.append(json.loads(line))
    all_vps=sorted(set(initial)|{c['vp'] for c in changes}); volumes=collections.Counter(c['vp'] for c in changes)
    # First pass: only positive <-> zero directed link transitions count as events.
    graphs={v:collections.Counter(initial.get(v,{})) for v in all_vps}; windows={};
    for c in changes:
        vp=c['vp'];t=c['timestamp'];g=graphs[vp]
        for a,b,delta in c['edge_weight_changes']:
            before=g[a,b];after=before+delta
            if after<0:raise ValueError('negative edge weight; change log inconsistent')
            if (before==0 and after>0) or (before>0 and after==0):
                kind='new_edge' if before==0 else 'outage'; key=(kind,a,b); groups=windows.setdefault(key,[])
                if not groups or t-groups[-1]['start']>args.window:groups.append({'type':kind,'a':a,'b':b,'start':t,'end':t,'vps':set()})
                groups[-1]['end']=t;groups[-1]['vps'].add(vp)
            if after:g[a,b]=after
            elif (a,b) in g:del g[a,b]
    candidates=[]
    for groups in windows.values():
        for e in groups:
            if 0<len(e['vps'])<len(all_vps)*.5:candidates.append(e)
    candidates.sort(key=lambda e:(-len(e['vps']),e['start'],e['type'],e['a'],e['b']))
    selected=[]
    for e in candidates:
        if all(e['end']<o['start'] or e['start']>o['end'] for o in selected):selected.append(e)
        if len(selected)>=args.max_events:break
    selected.sort(key=lambda e:e['start']);print('Events selected:',len(selected),'VPs:',len(all_vps),flush=True)
    if not selected:raise RuntimeError('no eligible non-overlapping events')
    # Take snapshots immediately before all updates at start second and after all updates at end second.
    snapshots={}; graphs={v:collections.Counter(initial.get(v,{})) for v in all_vps};i=0
    for e in selected:
        while i<len(changes) and changes[i]['timestamp']<e['start']:
            c=changes[i];g=graphs[c['vp']]
            for a,b,d in c['edge_weight_changes']:
                value=g[a,b]+d
                if value<0:raise ValueError('negative edge weight')
                if value:g[a,b]=value
                elif (a,b) in g:del g[a,b]
            i+=1
        before={v:dict(graphs[v]) for v in all_vps}
        while i<len(changes) and changes[i]['timestamp']<=e['end']:
            c=changes[i];g=graphs[c['vp']]
            for a,b,d in c['edge_weight_changes']:
                value=g[a,b]+d
                if value<0:raise ValueError('negative edge weight')
                if value:g[a,b]=value
                elif (a,b) in g:del g[a,b]
            i+=1
        snapshots[(e['start'],e['end'])]=(before,{v:dict(graphs[v]) for v in all_vps})
    dist={(a,b):0.0 for a in all_vps for b in all_vps}; feature_rows=[]
    for k,e in enumerate(selected):
        print('Computing event features',k+1,'/',len(selected),flush=True)
        before,after=snapshots[(e['start'],e['end'])]; raw=[]
        for v in all_vps:
            fb=features(before[v],e['a'],e['b']);fa=features(after[v],e['a'],e['b'])
            diff=[x-y for x,y in zip(fb,fa)];raw.append(diff)
            feature_rows.append({'event':k,'vp':v,'values':diff})
        scaled=standardize(raw)
        for i,a in enumerate(all_vps):
            for j in range(i+1,len(all_vps)):
                b=all_vps[j];d=math.sqrt(sum((x-y)**2 for x,y in zip(scaled[i],scaled[j])))/len(selected)
                dist[a,b]+=d;dist[b,a]+=d
    anchors,meta=select_anchors(all_vps,dist,volumes)
    out=ROOT/'results/topology_anchor';out.mkdir(parents=True,exist_ok=True)
    serial_events=[{**e,'vps':sorted(e['vps'])} for e in selected]
    result={'candidate_count':len(candidates),'selected_events':serial_events,'vp_count':len(all_vps),'anchors':anchors,'selection_parameters':meta,'runtime_seconds':round(time.time()-start,2),'limitations':'20 selected IPv4 prefixes, binary zero-crossing link events, 100s correlation and no AS-class balancing or origin-change events; undirected graph approximation; weight as strength with inverse distance; missing nodes and unreachable metrics assigned zero/reachable-component conventions; VP volume estimated from state-changing messages; standardization and selection follow paper framework but not exact implementation.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'features.jsonl').open('w') as f:
        for row in feature_rows:f.write(json.dumps(row)+'\n')
    print(json.dumps({'candidate_count':len(candidates),'selected_events':len(selected),'vp_count':len(all_vps),'anchors':len(anchors),'runtime_seconds':result['runtime_seconds']},indent=2))
if __name__=='__main__':main()
