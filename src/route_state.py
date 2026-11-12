"""Incremental per-peer IPv4 routing graph, independent of MRT decoder."""
from collections import Counter, defaultdict

class RouteState:
    def __init__(self):
        self.routes={}
        self.edges=Counter()
        self.peer_edges=defaultdict(Counter)
    @staticmethod
    def links(path):
        seq=[]
        for asn in path:
            if not seq or seq[-1]!=asn: seq.append(asn)
        return set(zip(seq,seq[1:]))
    def _remove(self,key):
        old=self.routes.pop(key,None)
        if old is not None:
            for edge in self.links(old):
                self.edges[edge]-=1
                if not self.edges[edge]: del self.edges[edge]
                self.peer_edges[key[0]][edge]-=1
                if not self.peer_edges[key[0]][edge]: del self.peer_edges[key[0]][edge]
        return old
    def announce(self,peer,prefix,path):
        key=(peer,prefix); old=self._remove(key); path=tuple(path)
        self.routes[key]=path
        for edge in self.links(path):
            self.edges[edge]+=1
            self.peer_edges[peer][edge]+=1
        return old
    def withdraw(self,peer,prefix):
        return self._remove((peer,prefix))
    def snapshot(self, peer=None):
        if peer is None: return dict(self.edges)
        return dict(self.peer_edges.get(peer,{}))
