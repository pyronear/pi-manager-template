"""Configure the device connection (device_ip + camera_ip) of every camera so the
alert API can reach it for livestreaming.

For each engine in the sister repo:
  - device_ip = the engine's VPN IP (``ansible_host`` in ``inventory/hosts_prod``).
    Only ``192.168.255.x`` VPN addresses are used; engines whose ``ansible_host``
    is a LAN/temporary IP are skipped and reported (their device_ip would not be
    reachable from the API).
  - for each camera in the engine's ``config_json``:
      camera_ip = the config_json key (camera IP on the engine's local network)
      camera_id = resolved from the API by camera name
  - PATCH /api/v1/cameras/{camera_id}/device_config {camera_ip, device_ip}

Dry-run by default (prints every planned PATCH); pass --apply to send them.

Env (init_script/.env): API_URL, SUPERADMIN_LOGIN, SUPERADMIN_PWD.
"""

import argparse
import json
import os
from pathlib import Path

import yaml
from common import api_request, get_token
from dotenv import load_dotenv

VPN_PREFIX = "192.168.255."
DEFAULT_REPO = Path.home() / "pyronear" / "devops" / "pi-manager-chile"


def load_inventory_hosts(repo: Path) -> dict:
    """Return {hostname: ansible_host} from inventory/hosts_prod."""
    doc = yaml.safe_load((repo / "inventory" / "hosts_prod").read_text()) or {}
    all_hosts = (doc.get("all") or {}).get("hosts") or {}
    return {name: (v or {}).get("ansible_host") for name, v in all_hosts.items()}


def parse_config_json(vars_yml: Path) -> dict | None:
    """Return the parsed config_json of a host, or None if it has none."""
    doc = yaml.safe_load(vars_yml.read_text()) or {}
    raw = doc.get("config_json")
    return json.loads(raw) if raw else None


def build_plan(repo: Path, name_to_id: dict) -> tuple[list, list]:
    """Return (planned, skipped) where planned items carry all PATCH fields."""
    inventory = load_inventory_hosts(repo)
    planned, skipped = [], []

    for engine_dir in sorted((repo / "host_vars").iterdir()):
        vars_yml = engine_dir / "vars.yml"
        if not vars_yml.exists():
            continue
        config = parse_config_json(vars_yml)
        if not config:  # not an engine (no cameras)
            continue

        engine = engine_dir.name
        device_ip = inventory.get(engine)
        if not device_ip or not device_ip.startswith(VPN_PREFIX):
            skipped.append((engine, f"engine ansible_host is not a VPN IP ({device_ip})"))
            continue

        for camera_ip, cam in config.items():
            name = cam.get("name")
            camera_id = name_to_id.get(name)
            if camera_id is None:
                skipped.append((engine, f"camera '{name}' ({camera_ip}) not found in the API"))
                continue
            cfg_id = cam.get("id")
            if cfg_id and str(cfg_id) != str(camera_id):
                print(f"WARN {engine}/{name}: config_json id={cfg_id} != API id={camera_id}; using API id")
            planned.append(
                {
                    "engine": engine,
                    "name": name,
                    "camera_id": camera_id,
                    "camera_ip": camera_ip,
                    "device_ip": device_ip,
                }
            )
    return planned, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Send the PATCH requests (default: dry-run)")
    parser.add_argument("--repo", default=str(DEFAULT_REPO), help="Path to the sister pi-manager repo")
    args = parser.parse_args()

    load_dotenv(override=True)
    api_url = (os.getenv("API_URL") or "").rstrip("/")
    login = os.getenv("SUPERADMIN_LOGIN")
    pwd = os.getenv("SUPERADMIN_PWD")
    if not (api_url and login and pwd):
        raise SystemExit("API_URL, SUPERADMIN_LOGIN and SUPERADMIN_PWD must be set in init_script/.env")

    auth = {
        "Authorization": f"Bearer {get_token(api_url, login, pwd)}",
        "Content-Type": "application/json",
    }

    cameras = api_request("get", f"{api_url}/api/v1/cameras/?include_non_trustable=true", auth)
    name_to_id, duplicates = {}, set()
    for cam in cameras:
        if cam["name"] in name_to_id:
            duplicates.add(cam["name"])
        name_to_id[cam["name"]] = cam["id"]
    for name in sorted(duplicates):
        print(f"WARN duplicate camera name in the API: '{name}' (last id wins)")

    repo = Path(args.repo).expanduser()
    planned, skipped = build_plan(repo, name_to_id)

    for item in planned:
        print(
            f"[plan] {item['engine']}/{item['name']} -> PATCH cameras/{item['camera_id']} "
            f"camera_ip={item['camera_ip']} device_ip={item['device_ip']}"
        )
    for engine, reason in skipped:
        print(f"[skip] {engine}: {reason}")
    print(f"\n{len(planned)} camera(s) to configure, {len(skipped)} skipped.")

    if not args.apply:
        print("Dry-run: re-run with --apply to send the PATCH requests.")
        return

    ok = errors = 0
    for item in planned:
        route = f"{api_url}/api/v1/cameras/{item['camera_id']}/device_config"
        payload = {"camera_ip": item["camera_ip"], "device_ip": item["device_ip"]}
        try:
            api_request("patch", route, auth, payload)
            print(f"[ok] {item['engine']}/{item['name']} (id {item['camera_id']}) configured")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - report and continue with the rest
            print(f"[error] {item['engine']}/{item['name']} (id {item['camera_id']}): {exc}")
            errors += 1
    print(f"\nApplied: {ok} ok, {errors} error(s).")


if __name__ == "__main__":
    main()
