"""CLI para gerenciar chaves e iniciar a API."""
import argparse, json, os
from pathlib import Path
from .keys import APIKeyStore
ROOT=Path(__file__).resolve().parents[1]
def store_from_env():
    return APIKeyStore(Path(os.getenv("NIXLMS_DATA_DIR",str(ROOT/"data"))).expanduser()/"api_keys.sqlite3")
def main(argv=None):
    parser=argparse.ArgumentParser(prog="nixlms-api",description="Gerenciador da API NixLMs")
    sub=parser.add_subparsers(dest="command",required=True)
    create=sub.add_parser("keygen"); create.add_argument("--label",required=True); create.add_argument("--scopes",default="chat:read,chat:write,models:read"); create.add_argument("--ttl-days",type=int)
    sub.add_parser("keys")
    revoke=sub.add_parser("revoke"); revoke.add_argument("prefix")
    sub.add_parser("serve")
    args=parser.parse_args(argv)
    if args.command=="serve":
        from .server import main as serve
        serve(); return 0
    store=store_from_env()
    if args.command=="keygen":
        result=store.create(args.label,[x.strip() for x in args.scopes.split(",") if x.strip()],args.ttl_days)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        print("\nGUARDE A CHAVE AGORA: ela não poderá ser exibida novamente."); return 0
    if args.command=="keys": print(json.dumps(store.list(),ensure_ascii=False,indent=2)); return 0
    if args.command=="revoke":
        if not store.revoke(args.prefix): parser.error("Prefixo não encontrado ou já revogado.")
        print("Chave revogada."); return 0
    return 2
if __name__=="__main__": raise SystemExit(main())
