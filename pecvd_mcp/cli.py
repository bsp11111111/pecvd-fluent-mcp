import argparse
import json
from datetime import datetime
from pathlib import Path

from .bridge import bridge, PACKAGE_ROOT
from .model import baseline, conversions


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['doctor','baseline','prepare','mcp-config'])
    parser.add_argument('--project-id')
    args=parser.parse_args()
    if args.action=='doctor':
        result=bridge.doctor()
        (PACKAGE_ROOT/'environment-report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    elif args.action=='baseline':result={'reference':baseline(),'conversions':conversions()}
    elif args.action=='prepare':result=bridge.new_project(args.project_id or 'first-check-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    else:
        python=PACKAGE_ROOT/'.venv/Scripts/python.exe'
        result={'mcpServers':{'pecvd-fluent':{'command':str(python),'args':['-m','pecvd_mcp.server'],'env':{'PECVD_WORKSPACE':str(PACKAGE_ROOT/'runs'),'PECVD_PACKAGE_ROOT':str(PACKAGE_ROOT)}}}}
        (PACKAGE_ROOT/'mcp-config.generated.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
