#!/usr/bin/env python3
"""Filter normalized JSONL events from stdin using a saved pipeline report."""
import argparse,json,sys
from pipeline import apply_policy

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--policy',required=True,help='path to pipeline report.json')
 parser.add_argument('--discard-log',help='optional JSONL destination for dropped records')
 args=parser.parse_args()
 with open(args.policy) as f: policy=json.load(f)
 anchors=set(policy['anchors']);drops={tuple(p) for p in policy['drop_pairs']}
 dropped=open(args.discard_log,'w') if args.discard_log else None
 try:
  for line_no,line in enumerate(sys.stdin,1):
   if not line.strip():continue
   try:
    event=json.loads(line); vp=event['vp'];prefix=event['prefix']
    if not isinstance(vp,str) or not isinstance(prefix,str):raise ValueError('vp and prefix must be strings')
   except (ValueError,KeyError,TypeError) as exc:
    print(f'line {line_no}: invalid record: {exc}',file=sys.stderr);return 2
   sink=sys.stdout if apply_policy(vp,prefix,anchors,drops) else dropped
   if sink: sink.write(json.dumps(event,ensure_ascii=False)+'\n');sink.flush()
 finally:
  if dropped:dropped.close()
 return 0
if __name__=='__main__':sys.exit(main())
