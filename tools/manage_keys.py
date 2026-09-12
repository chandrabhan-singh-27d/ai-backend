import argparse

from app.services.api_keys import get_api_keys_store


def cmd_create(args: argparse.Namespace) -> None:
    key = get_api_keys_store().create(args.name)
    print(f"Created Key '{args.name}':")
    print(key)
    print("Please store your key as this will not be shown afterwards for security purposes")


def cmd_list(args: argparse.Namespace) -> None:
    rows = get_api_keys_store().list_all()
    if not rows:
        print("No Keys.")
        return
    print(f"{'ID':<4} {'NAME':<18} {'PREFIX':<9} FINGERPRINT STATUS   CREATED_AT")
    for row in rows:
        print(
            f"{row['id']:<4} {row['name']:<18} {row['prefix']:<9} "
            f"{row['fingerprint']}   {'revoked' if row['revoked'] else 'active':<7} "
            f"  {row['created_at']}"
        )
def cmd_revoke(args: argparse.Namespace) -> None:
    get_api_keys_store().revoke(args.key_id)
    print(f"Revoked key id {args.key_id}.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Manage AI Backend API Keys")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="create a new key")
    p_create.add_argument("name", help="owner/app name")
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="list all keys")
    p_list.set_defaults(func=cmd_list)

    p_revoke = sub.add_parser("revoke", help="revoke a key")
    p_revoke.add_argument("key_id", type=int, help="numeric key id from 'list")
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()