"""Apply decoded ordinary IPv4 BGP announcements and withdrawals to RouteState."""
from route_state import RouteState

def apply_message(state, d):
    msg=d.get('bgp_message',{})
    if 2 not in msg.get('type',{}): return {'announced':0,'withdrawn':0,'unsupported':0}
    vp=str(d.get('peer_as'))+'@'+str(d.get('peer_ip'))
    result={'announced':0,'withdrawn':0,'unsupported':0}
    for p in msg.get('withdrawn_routes',[]):
        state.withdraw(vp,str(p['prefix'])+'/'+str(p['length']));result['withdrawn']+=1
    announcements=msg.get('nlri',[])
    if announcements:
        paths=[a.get('value',[]) for a in msg.get('path_attributes',[]) if 2 in a.get('type',{})]
        if len(paths)!=1 or any(2 not in s.get('type',{}) for s in paths[0]):
            result['unsupported']+=len(announcements)
            for p in announcements: state.withdraw(vp,str(p['prefix'])+'/'+str(p['length']))
        else:
            path=tuple(str(v) for seg in paths[0] for v in seg.get('value',[]))
            for p in announcements:
                state.announce(vp,str(p['prefix'])+'/'+str(p['length']),path);result['announced']+=1
    return result
