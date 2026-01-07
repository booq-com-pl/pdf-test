#/usr/bin/env python3

# Example usage:
# export TENANT_ID="..."
# export CLIENT_ID="..."
# export CLIENT_SECRET="..."

# python upload_sp.py --acronym JanosS ./PIT2_JKowalski.pdf
# python upload_sp.py --acronym JanosS --dir ./outputfiles


import os
import sys
import argparse
import urllib.parse
import requests
import msal
from pathlib import Path

GRAPH = "https://graph.microsoft.com/v1.0"

def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=authority,
        client_credential=client_secret,
    )
    token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in token:
        raise RuntimeError(f"Token error: {token}")
    return token["access_token"]

def graph_get(url: str, token: str, params=None):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def graph_post(url: str, token: str, json_body: dict):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=json_body)
    r.raise_for_status()
    return r.json()

def graph_put_bytes(url: str, token: str, data: bytes):
    r = requests.put(url, headers={"Authorization": f"Bearer {token}"}, data=data)
    r.raise_for_status()
    return r.json()

def resolve_site_id(token: str, hostname: str, site_path: str) -> str:
    url = f"{GRAPH}/sites/{hostname}:/sites/{site_path}"
    js = graph_get(url, token)
    if not js:
        raise RuntimeError(f"Nie znaleziono site: {hostname}:/sites/{site_path}")
    return js["id"]

def resolve_drive_id_by_name(token: str, site_id: str, drive_name: str) -> str:
    url = f"{GRAPH}/sites/{site_id}/drives"
    js = graph_get(url, token)
    drives = (js or {}).get("value", [])
    for d in drives:
        if d.get("name") == drive_name:
            return d["id"]
    available = [d.get("name") for d in drives]
    raise RuntimeError(f"Nie znaleziono biblioteki '{drive_name}'. Dostępne: {available}")

def item_exists(token: str, drive_id: str, path_in_drive: str) -> bool:
    # GET /drives/{drive-id}/root:/{path}
    encoded_path = urllib.parse.quote(path_in_drive.strip("/"))
    url = f"{GRAPH}/drives/{drive_id}/root:/{encoded_path}"
    js = graph_get(url, token)
    return js is not None

def ensure_folder(token: str, drive_id: str, parent_folder: str, folder_name: str) -> str:
    """
    Zapewnia istnienie folderu parent_folder/folder_name.
    Zwraca ścieżkę docelową w bibliotece (path).
    """
    parent_folder = parent_folder.strip("/")

    full_path = f"{parent_folder}/{folder_name}" if parent_folder else folder_name

    # jeśli istnieje, nic nie rób
    if item_exists(token, drive_id, full_path):
        return full_path

    # utwórz: POST /drives/{drive-id}/root:/{parent}:/children
    # body: { "name": "...", "folder": {}, "@microsoft.graph.conflictBehavior": "fail" }
    encoded_parent = urllib.parse.quote(parent_folder) if parent_folder else ""
    if encoded_parent:
        url = f"{GRAPH}/drives/{drive_id}/root:/{encoded_parent}:/children"
    else:
        url = f"{GRAPH}/drives/{drive_id}/root/children"

    body = {
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "fail",
    }

    try:
        graph_post(url, token, body)
    except requests.HTTPError as e:
        # jeśli w międzyczasie ktoś utworzył, potraktuj jako ok
        if e.response is not None and e.response.status_code in (409,):
            pass
        else:
            raise

    return full_path

def upload_small_file(token: str, drive_id: str, dest_path_in_drive: str, local_file: str):
    with open(local_file, "rb") as f:
        data = f.read()

    encoded_path = urllib.parse.quote(dest_path_in_drive.strip("/"))
    url = f"{GRAPH}/drives/{drive_id}/root:/{encoded_path}:/content"
    return graph_put_bytes(url, token, data)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tenant-id", default=os.getenv("TENANT_ID"))
    p.add_argument("--client-id", default=os.getenv("CLIENT_ID"))
    p.add_argument("--client-secret", default=os.getenv("CLIENT_SECRET"))

    # Z Twojego linku:
    p.add_argument("--hostname", default="booqpoznan.sharepoint.com")
    p.add_argument("--site-path", default="AplicationDeployment")      # /sites/AplicationDeployment
    p.add_argument("--drive-name", default="Biblioteka dokumentów")     # nazwa biblioteki (drive)
    p.add_argument("--base-folder", default="Pracownicy")              # folder bazowy w bibliotece
    p.add_argument("--acronym", required=True, help="Nazwa katalogu do utworzenia pod Pracownicy/")

    p.add_argument("--dir", dest="dir", help="Lokalny katalog do uploadu (jeden poziom, tylko PDF)")
    p.add_argument("file", nargs="?", help="lokalna ścieżka do pliku do uploadu (gdy nie używasz --dir)")
    args = p.parse_args()

    print(f"Arguments: tenant_id={args.tenant_id}, client_id={args.client_id}, hostname={args.hostname}, site_path={args.site_path}, drive_name={args.drive_name}, base_folder={args.base_folder}, acronym={args.acronym}, dir={args.dir}, file={args.file}")

    if not args.tenant_id or not args.client_id or not args.client_secret:
        print("Brak TENANT_ID/CLIENT_ID/CLIENT_SECRET (parametry lub zmienne env).", file=sys.stderr)
        sys.exit(2)

    token = get_token(args.tenant_id, args.client_id, args.client_secret)

    site_id = resolve_site_id(token, args.hostname, args.site_path)
    drive_id = resolve_drive_id_by_name(token, site_id, args.drive_name)

    # upewnij się, że istnieje Pracownicy/<acronym>
    target_folder = ensure_folder(token, drive_id, args.base_folder, args.acronym)

    # Upload either a directory (one level, PDFs only) or a single file.
    if args.dir:
        local_dir = Path(args.dir)
        if not local_dir.exists() or not local_dir.is_dir():
            print(f"--dir must point to an existing directory: {args.dir}", file=sys.stderr)
            sys.exit(2)

        pdfs = [p for p in sorted(local_dir.iterdir()) if p.is_file() and p.suffix.lower() == ".pdf"]
        if not pdfs:
            print(f"No PDF files found in directory: {local_dir}")
            return

        for pth in pdfs:
            dest = f"{target_folder}/{pth.name}"
            print("Uploading:", str(pth), "->", dest)
            result = upload_small_file(token, drive_id, dest, str(pth))
            print("OK:", result.get("webUrl") or result.get("name"))

    else:
        if not args.file:
            print("Provide either --dir <folder> or <file>", file=sys.stderr)
            sys.exit(2)

        filename = os.path.basename(args.file)
        dest = f"{target_folder}/{filename}"

        # UWAGA: dla >~4MB zrób upload session (chunked). Tu: małe pliki.
        result = upload_small_file(token, drive_id, dest, args.file)

        print("OK:", result.get("webUrl") or result.get("name"))

if __name__ == "__main__":
    main()