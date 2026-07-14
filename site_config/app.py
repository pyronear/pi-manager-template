"""Pyronear station setup app.

Single-page Streamlit wizard that takes a new engine site from zero to
`make init-one-engine`: create org/user/cameras in the alert API, write
host_vars/<site>/ and inventory/hosts_prod in the sister repo, then launch
the init playbook through the pyro-ansible container.

Run with:
    uv run --with streamlit,pyyaml,requests streamlit run site_config/app.py

All non-secret inputs and API results are auto-saved to a per-site draft
(site_config/drafts/<site>.json) so nothing is lost if Streamlit restarts.
Secrets are kept in memory only and must be re-entered after a restart.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
DRAFTS_DIR = APP_DIR / "drafts"

sys.path.insert(0, str(REPO_ROOT / "init_script"))
from common import api_request, get_token  # noqa: E402

ADAPTERS = [
    "reolink-823S2",
    "reolink-823A16",
    "reolink-810a",
    "reolink-duo2",
    "reolink-915A?",
    "linovision",
    "url",
]

# children of `all` in hosts_prod that are infrastructure, not site groups
INFRA_GROUPS = {
    "engine_servers",
    "alert_server",
    "alert_server_preprod",
    "alert_api_servers",
    "annotation_server",
    "platform_py_server",
    "platform_react_server",
    "openvpn",
    "mediamtx_server",
    "temporal_server",
    "pi_zero",
    "envprod",
}

SECRET_KEYS = {"pi_password", "vpn_password", "cam_pwd", "wifi_password", "user_password"}

SIMPLE_DRAFT_KEYS = [
    "site_name", "num_cams", "latlon", "elevation", "aov", "n_poses", "cam_type",
    "is_trustable", "org_name", "user_login", "user_role", "repo_path", "cam_user",
    "wifi_ssid", "static_iface", "static_ip", "static_gw", "watchdog", "shelly_ip",
    "group_choice", "new_group", "ssh_port", "pi_local_ip",
]
DYNAMIC_KEY_RE = re.compile(r"^(ip|adapter|adapter_custom)_\d+$")

NEW_DRAFT = "— new site —"
NO_GROUP = "(none)"
NEW_GROUP = "New group..."


# ---------------------------------------------------------------- helpers

def read_env_file(path: Path) -> dict:
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def resolve_path(value: str) -> Path:
    """Paths in .env are relative to the template repo root."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def yaml_str(value: str) -> str:
    """Safely double-quote a value for YAML (JSON strings are valid YAML)."""
    return json.dumps(value, ensure_ascii=False)


def compute_azimuths(cam_index: int, total_ptz: int, n_poses: int) -> list[int]:
    """Evenly spaced azimuths for a camera, split across all PTZ cameras."""
    total_positions = total_ptz * n_poses
    step = 360 / total_positions
    start = cam_index * n_poses
    return [round(step * (start + j)) % 360 for j in range(n_poses)]


def parse_latlon(raw: str) -> tuple[float, float]:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        raise ValueError("expected 'lat,lon'")
    return float(parts[0]), float(parts[1])


# ---------------------------------------------------------------- drafts

def save_draft() -> None:
    site = str(st.session_state.get("site_name", "")).strip()
    if not site:
        return
    fields = {
        k: st.session_state[k]
        for k in st.session_state
        if (k in SIMPLE_DRAFT_KEYS or DYNAMIC_KEY_RE.match(k)) and k not in SECRET_KEYS
    }
    data = {"version": 1, "fields": fields, "results": st.session_state.get("results", {})}
    DRAFTS_DIR.mkdir(exist_ok=True)
    tmp = DRAFTS_DIR / f".{site}.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(DRAFTS_DIR / f"{site}.json")


def load_draft_cb() -> None:
    name = st.session_state.get("draft_pick")
    if not name or name == NEW_DRAFT:
        return
    path = DRAFTS_DIR / f"{name}.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for key, val in data.get("fields", {}).items():
        st.session_state[key] = val
    st.session_state["results"] = data.get("results", {})


# ---------------------------------------------------------------- API actions

def api_auth(api_url: str, login: str, pwd: str) -> dict:
    token = get_token(api_url, login, pwd)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_or_create_org(api_url: str, auth: dict, org_name: str) -> tuple[int, bool]:
    orgs = api_request("get", f"{api_url}/api/v1/organizations/", auth)
    for org in orgs:
        if org["name"] == org_name:
            return org["id"], False
    resp = api_request("post", f"{api_url}/api/v1/organizations/", auth, {"name": org_name})
    return resp["id"], True


def create_cameras(api_url: str, auth: dict, org_id: int, cams: list[dict],
                   site_vals: dict, prev_results: dict) -> tuple[dict, list[str]]:
    """Create cameras + poses, returning {name: {id, pose_ids}} and log lines."""
    existing = api_request("get", f"{api_url}/api/v1/cameras/?include_non_trustable=true", auth)
    existing_by_name = {c["name"]: c for c in existing if c["organization_id"] == org_id}

    results, logs = {}, []
    total_ptz = len(cams) if site_vals["n_poses"] > 0 else 0
    ptz_index = 0
    for cam in cams:
        name = cam["name"]
        if name in existing_by_name:
            prev = prev_results.get(name, {})
            results[name] = {
                "id": existing_by_name[name]["id"],
                "pose_ids": prev.get("pose_ids", []),
            }
            logs.append(f"Camera '{name}' already exists (id {results[name]['id']}), skipped.")
            if site_vals["n_poses"] > 0:
                ptz_index += 1
            continue

        payload = {
            "organization_id": org_id,
            "name": name,
            "angle_of_view": site_vals["aov"],
            "elevation": site_vals["elevation"],
            "lat": site_vals["lat"],
            "lon": site_vals["lon"],
            "is_trustable": site_vals["is_trustable"],
        }
        resp = api_request("post", f"{api_url}/api/v1/cameras/", auth, payload)
        cam_id = resp["id"]
        pose_ids = []
        if site_vals["n_poses"] > 0:
            azimuths = compute_azimuths(ptz_index, total_ptz, site_vals["n_poses"])
            for patrol_id, azimuth in enumerate(azimuths):
                pose = api_request(
                    "post", f"{api_url}/api/v1/poses/", auth,
                    {"camera_id": cam_id, "azimuth": azimuth, "patrol_id": patrol_id},
                )
                pose_ids.append(pose["id"])
            ptz_index += 1
        results[name] = {"id": cam_id, "pose_ids": pose_ids}
        logs.append(f"Camera '{name}' created: id {cam_id}, pose_ids {pose_ids}")
    return results, logs


# ---------------------------------------------------------------- file generation

def build_vars_yml(cams: list[dict], results: dict, site_vals: dict) -> str:
    config = {}
    for cam in cams:
        res = results.get(cam["name"], {})
        entry = {"pose_ids": res.get("pose_ids", [])}
        if site_vals["cam_type"] == "static":
            entry["azimuth"] = cam["azimuth"]
        entry.update({
            "adapter": cam["adapter"],
            "id": str(res.get("id", "")),
            "name": cam["name"],
            "bbox_mask_url": "",
            "poses": list(range(site_vals["n_poses"])) if site_vals["cam_type"] == "ptz" else [],
            "token": "",
            "type": site_vals["cam_type"],
        })
        config[cam["ip"]] = entry

    json_block = json.dumps(config, indent=4, ensure_ascii=False)
    indented = "\n".join("    " + line for line in json_block.splitlines())
    out = f"config_json: |\n{indented}\n\n"
    out += f"static_ip_interface: {site_vals['static_iface']}\n"
    out += f"static_ip_address: {site_vals['static_ip']}\n"
    out += f"static_ip_gateway: {site_vals['static_gw']}\n"
    if site_vals["watchdog"] == "shelly":
        out += "\nshelly_enabled: true\n"
        out += f"shelly_watchdog_ip: {yaml_str(site_vals['shelly_ip'])}\n"
    return out


def build_vault_yml(secrets: dict) -> str:
    return (
        f"ansible_password: {yaml_str(secrets['pi_password'])}\n"
        'ansible_become_password: "{{ ansible_password }}"\n'
        "\n"
        "##### ENGINE\n"
        f"CAM_USER: {yaml_str(secrets['cam_user'])}\n"
        f"CAM_PWD: {yaml_str(secrets['cam_pwd'])}\n"
        f"open_vpn_password: {yaml_str(secrets['vpn_password'])}\n"
        "## VPN\n"
        'openvpn_client_password: "{{ open_vpn_password }}"\n'
        "\n"
        "wifi_connections:\n"
        f"  - ssid: {yaml_str(secrets['wifi_ssid'])}\n"
        f"    password: {yaml_str(secrets['wifi_password'])}\n"
        "    priority: 10\n"
    )


def encrypt_vault(path: Path, content: str, vault_password_file: Path | None) -> bool:
    """Write vault content, encrypting via ansible-vault. Returns True if encrypted."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content)
    if (
        vault_password_file
        and vault_password_file.exists()
        and shutil.which("ansible-vault")
    ):
        proc = subprocess.run(
            ["ansible-vault", "encrypt", str(tmp),
             "--vault-password-file", str(vault_password_file)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"ansible-vault encrypt failed: {proc.stderr.strip()}")
        tmp.replace(path)
        return True
    tmp.replace(path)
    return False


# ---------------------------------------------------------------- hosts_prod editing

def insert_after(text: str, anchor: str, insertion: str) -> str:
    match = re.search(anchor, text, flags=re.M)
    if not match:
        raise ValueError(f"anchor not found in hosts_prod: {anchor!r}")
    return text[: match.end()] + insertion + text[match.end():]


def insert_before(text: str, anchor: str, insertion: str) -> str:
    match = re.search(anchor, text, flags=re.M)
    if not match:
        raise ValueError(f"anchor not found in hosts_prod: {anchor!r}")
    return text[: match.start()] + insertion + text[match.start():]


def update_hosts_prod(inv_path: Path, site: str, ip: str, port: int,
                      group: str | None) -> list[str]:
    """Idempotently add the host to hosts_prod. Returns list of applied changes."""
    text = inv_path.read_text()
    data = yaml.safe_load(text)
    hosts = data["all"].get("hosts") or {}
    children = data["all"].get("children") or {}
    changes = []

    if site not in hosts:
        entry = f"    {site}:\n      ansible_host: {ip}\n      reverse_ssh_port: {port}\n"
        text = insert_after(text, r"^all:\n  hosts:\n", entry)
        changes.append("host entry under all.hosts")

    engine_hosts = (children.get("engine_servers") or {}).get("hosts") or {}
    if site not in engine_hosts:
        text = insert_after(text, r"^    engine_servers:\n      hosts:\n", f"        {site}:\n")
        changes.append("engine_servers membership")

    if group:
        group_hosts = (children.get(group) or {}).get("hosts") or {}
        if group in children and site not in group_hosts:
            text = insert_after(
                text, rf"^    {re.escape(group)}:\n      hosts:\n", f"        {site}:\n"
            )
            changes.append(f"'{group}' membership")
        elif group not in children:
            block = f"    {group}:\n      hosts:\n        {site}:\n\n"
            try:
                text = insert_before(text, r"^    alert_server:\n", block)
            except ValueError:
                text = insert_before(text, r"^    envprod:\n", block)
            changes.append(f"new group '{group}'")

    if not changes:
        return []

    # validate before touching the file
    new_data = yaml.safe_load(text)
    new_hosts = new_data["all"]["hosts"]
    new_engines = new_data["all"]["children"]["engine_servers"]["hosts"]
    if site not in new_hosts or site not in new_engines:
        raise RuntimeError("hosts_prod validation failed after edit, file left untouched")

    tmp = inv_path.with_name(inv_path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(inv_path)
    return changes


def next_ssh_port(inv_path: Path) -> int:
    data = yaml.safe_load(inv_path.read_text())
    ports = [
        h["reverse_ssh_port"]
        for h in (data["all"].get("hosts") or {}).values()
        if isinstance(h, dict) and isinstance(h.get("reverse_ssh_port"), int)
    ]
    return max(ports, default=2220) + 1


def site_groups(inv_path: Path) -> list[str]:
    data = yaml.safe_load(inv_path.read_text())
    children = data["all"].get("children") or {}
    return sorted(g for g in children if g not in INFRA_GROUPS)


# ---------------------------------------------------------------- UI

def main() -> None:
    st.set_page_config(page_title="Pyronear Station Setup", layout="wide")
    st.title("Pyronear Station Setup")

    root_env = read_env_file(REPO_ROOT / ".env")
    script_env = read_env_file(REPO_ROOT / "init_script" / ".env")
    api_url = (script_env.get("API_URL") or "").rstrip("/")
    superadmin_login = script_env.get("SUPERADMIN_LOGIN", "")
    superadmin_pwd = script_env.get("SUPERADMIN_PWD", "")

    # ---- sidebar: drafts + progress
    DRAFTS_DIR.mkdir(exist_ok=True)
    drafts = sorted(p.stem for p in DRAFTS_DIR.glob("*.json"))
    st.sidebar.selectbox(
        "Resume a draft", [NEW_DRAFT] + drafts, key="draft_pick", on_change=load_draft_cb,
        help="Inputs are auto-saved per site (secrets excluded). Pick a site to resume.",
    )

    st.session_state.setdefault("results", {})

    # ---- 1. environment
    st.header("1. Environment")
    st.session_state.setdefault("repo_path", root_env.get("REPO_PATH", "../pi-manager-fr"))
    st.text_input("Sister repo path (pi-manager-X)", key="repo_path")
    repo = resolve_path(st.session_state["repo_path"])
    inv_path = repo / "inventory" / "hosts_prod"
    host_vars_dir = repo / "host_vars"

    col1, col2 = st.columns(2)
    with col1:
        if inv_path.exists() and host_vars_dir.exists():
            st.success(f"Sister repo found: {repo}")
        else:
            st.error(f"Not a valid sister repo (missing inventory/hosts_prod or host_vars): {repo}")
    with col2:
        if api_url and superadmin_login:
            st.info(f"API: {api_url} (login: {superadmin_login}, from init_script/.env)")
        else:
            st.error("API_URL / SUPERADMIN_LOGIN / SUPERADMIN_PWD missing in init_script/.env")

    env_repo = root_env.get("REPO_PATH")
    if env_repo and resolve_path(env_repo) != repo:
        st.warning(
            f"Root .env has REPO_PATH={env_repo} — the pyro-ansible container mounts that repo, "
            "not the one selected above. Fix .env and restart the container before launching."
        )

    # ---- 2. site info
    st.header("2. Site")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.setdefault("site_name", "")
        st.text_input("Site name", key="site_name", placeholder="sdis-tigery")
        st.session_state.setdefault("num_cams", 2)
        st.number_input("Number of cameras", min_value=1, max_value=20, key="num_cams")
    with c2:
        st.session_state.setdefault("latlon", "")
        st.text_input("Site location (lat,lon)", key="latlon", placeholder="34.0522,-118.2437")
        st.session_state.setdefault("elevation", 100.0)
        st.number_input("Elevation (m)", key="elevation")
    with c3:
        st.session_state.setdefault("aov", 54.2)
        st.number_input("Angle of view (°)", key="aov")
        st.session_state.setdefault("n_poses", 4)
        st.number_input("Poses per camera", min_value=0, max_value=12, key="n_poses")

    st.session_state.setdefault("cam_type", "ptz")
    st.radio("Camera type", ["ptz", "static"], key="cam_type", horizontal=True)
    st.session_state.setdefault("is_trustable", True)
    st.checkbox("Cameras are trustable", key="is_trustable")

    site = st.session_state["site_name"].strip()
    num_cams = int(st.session_state["num_cams"])
    n_poses = int(st.session_state["n_poses"]) if st.session_state["cam_type"] == "ptz" else 0

    cams = []
    cam_cols = st.columns(min(num_cams, 4))
    for i in range(num_cams):
        with cam_cols[i % len(cam_cols)]:
            st.subheader(f"Camera {i + 1}")
            st.session_state.setdefault(f"ip_{i}", f"192.168.1.{11 + i}")
            st.text_input("IP address", key=f"ip_{i}")
            st.session_state.setdefault(f"adapter_{i}", ADAPTERS[0])
            adapter = st.selectbox("Adapter", ADAPTERS + ["Other..."], key=f"adapter_{i}")
            if adapter == "Other...":
                st.session_state.setdefault(f"adapter_custom_{i}", "")
                adapter = st.text_input("Custom adapter", key=f"adapter_custom_{i}")
            cam = {
                "ip": st.session_state[f"ip_{i}"],
                "adapter": adapter,
                "name": f"{site}-{i + 1:02d}" if site else "",
            }
            if st.session_state["cam_type"] == "static":
                cam["azimuth"] = round(i * 360 / num_cams) % 360
            cams.append(cam)

    lat = lon = None
    try:
        lat, lon = parse_latlon(st.session_state["latlon"])
    except ValueError:
        st.warning("Enter the site location as 'lat,lon' (e.g. 34.0522,-118.2437)")

    site_vals = {
        "aov": float(st.session_state["aov"]),
        "elevation": float(st.session_state["elevation"]),
        "lat": lat,
        "lon": lon,
        "is_trustable": bool(st.session_state["is_trustable"]),
        "n_poses": n_poses,
        "cam_type": st.session_state["cam_type"],
    }

    # ---- 3. API creation
    st.header("3. Alert API — org, user, cameras")
    st.session_state.setdefault("org_name", script_env.get("organization_name", ""))
    st.text_input("Organization name", key="org_name")
    org_name = st.session_state["org_name"].strip()

    api_ready = bool(api_url and superadmin_login and superadmin_pwd)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Create organization", key="btn_org", disabled=not (api_ready and org_name)):
            try:
                auth = api_auth(api_url, superadmin_login, superadmin_pwd)
                org_id, created = get_or_create_org(api_url, auth, org_name)
                st.session_state["results"]["org_id"] = org_id
                st.success(f"Organization '{org_name}' {'created' if created else 'already exists'} (id {org_id})")
            except Exception as exc:  # surface API errors in the UI
                st.error(str(exc))
    with b2:
        org_id_known = st.session_state["results"].get("org_id")
        st.caption(f"Organization id: {org_id_known}" if org_id_known else "Organization not created yet")

    with st.expander("Create API user (optional)"):
        u1, u2, u3 = st.columns(3)
        with u1:
            st.session_state.setdefault("user_login", "")
            st.text_input("Login", key="user_login")
        with u2:
            st.text_input("Password", key="user_password", type="password")
        with u3:
            st.session_state.setdefault("user_role", "admin")
            st.text_input("Role", key="user_role")
        can_user = api_ready and org_name and st.session_state["user_login"] and st.session_state["user_password"]
        if st.button("Create user", key="btn_user", disabled=not can_user):
            try:
                auth = api_auth(api_url, superadmin_login, superadmin_pwd)
                org_id, _ = get_or_create_org(api_url, auth, org_name)
                api_request("post", f"{api_url}/api/v1/users/", auth, {
                    "organization_id": org_id,
                    "login": st.session_state["user_login"],
                    "password": st.session_state["user_password"],
                    "role": st.session_state["user_role"],
                })
                st.success(f"User '{st.session_state['user_login']}' created")
            except Exception as exc:
                st.error(str(exc))

    cameras_df = [
        {"name": c["name"], "ip": c["ip"], "angle_of_view": site_vals["aov"],
         "elevation": site_vals["elevation"], "lat": lat, "lon": lon,
         "is_trustable": site_vals["is_trustable"], "n_poses": n_poses}
        for c in cams
    ]
    st.dataframe(cameras_df, hide_index=True)

    can_create_cams = api_ready and org_name and site and lat is not None
    if st.button("Create cameras", key="btn_cams", type="primary", disabled=not can_create_cams):
        try:
            auth = api_auth(api_url, superadmin_login, superadmin_pwd)
            org_id, _ = get_or_create_org(api_url, auth, org_name)
            st.session_state["results"]["org_id"] = org_id
            prev = st.session_state["results"].get("cameras", {})
            results, logs = create_cameras(api_url, auth, org_id, cams, site_vals, prev)
            st.session_state["results"]["cameras"] = {**prev, **results}
            for line in logs:
                st.write(line)
            save_draft()
        except Exception as exc:
            st.error(str(exc))

    cam_results = st.session_state["results"].get("cameras", {})
    missing_ids = [c["name"] for c in cams if c["name"] and not cam_results.get(c["name"], {}).get("id")]
    if cam_results and not missing_ids:
        st.success(f"Camera ids captured: { {n: r['id'] for n, r in cam_results.items()} }")

    # ---- 4. secrets
    st.header("4. Secrets")
    st.caption("Kept in memory only — never written to drafts. Re-enter after a Streamlit restart.")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.text_input("Pi password (ansible_password)", key="pi_password", type="password")
        st.text_input("VPN password", key="vpn_password", type="password")
    with s2:
        st.session_state.setdefault("cam_user", "admin")
        st.text_input("Camera user", key="cam_user")
        st.session_state.setdefault("cam_pwd", "@Pyronear")
        st.text_input("Camera password", key="cam_pwd", type="password")
    with s3:
        st.session_state.setdefault("wifi_ssid", "Pyronear")
        st.text_input("Wifi SSID", key="wifi_ssid")
        st.session_state.setdefault("wifi_password", "@Pyronear")
        st.text_input("Wifi password", key="wifi_password", type="password")

    # ---- 5. host files
    st.header("5. Host files (sister repo)")
    h1, h2, h3 = st.columns(3)
    with h1:
        st.session_state.setdefault("static_iface", "eth0")
        st.text_input("Static IP interface", key="static_iface")
        st.session_state.setdefault("static_ip", "192.168.1.99")
        st.text_input("Static IP address", key="static_ip")
    with h2:
        st.session_state.setdefault("static_gw", "192.168.1.1")
        st.text_input("Static IP gateway", key="static_gw")
        st.session_state.setdefault("watchdog", "none")
        st.radio("Watchdog", ["none", "shelly"], key="watchdog", horizontal=True)
    with h3:
        st.session_state.setdefault("shelly_ip", "192.168.1.97")
        if st.session_state["watchdog"] == "shelly":
            st.text_input("Shelly IP", key="shelly_ip")
        st.session_state.setdefault("pi_local_ip", "192.168.1.99")
        st.text_input("Pi IP for setup (ansible_host)", key="pi_local_ip",
                      help="IP the Pi answers on during setup — used in hosts_prod and by init-one-engine.")

    site_vals.update({
        "static_iface": st.session_state["static_iface"],
        "static_ip": st.session_state["static_ip"],
        "static_gw": st.session_state["static_gw"],
        "watchdog": st.session_state["watchdog"],
        "shelly_ip": st.session_state["shelly_ip"],
    })

    site_dir = host_vars_dir / site if site else None

    if inv_path.exists():
        g1, g2 = st.columns(2)
        with g1:
            groups = site_groups(inv_path)
            options = [NO_GROUP] + groups + [NEW_GROUP]
            st.session_state.setdefault("group_choice", NO_GROUP)
            if st.session_state["group_choice"] not in options:
                st.session_state["group_choice"] = NO_GROUP
            st.selectbox("Site group in hosts_prod", options, key="group_choice")
            if st.session_state["group_choice"] == NEW_GROUP:
                st.session_state.setdefault("new_group", "")
                st.text_input("New group name", key="new_group", placeholder="sdis_91")
        with g2:
            st.session_state.setdefault("ssh_port", next_ssh_port(inv_path))
            st.number_input("reverse_ssh_port", min_value=2200, max_value=9999, key="ssh_port",
                            help="Auto-proposed as max existing port + 1.")

    overwrite = st.checkbox("Overwrite existing host_vars files", value=False)
    ready = bool(site and lat is not None and inv_path.exists())
    if missing_ids:
        st.warning(f"Cameras without API id yet (run 'Create cameras' first): {missing_ids}")

    f1, f2, f3 = st.columns(3)
    with f1:
        vars_exists = site_dir is not None and (site_dir / "vars.yml").exists()
        if st.button("Write vars.yml", key="btn_vars", disabled=not ready or (vars_exists and not overwrite)):
            site_dir.mkdir(parents=True, exist_ok=True)
            content = build_vars_yml(cams, cam_results, site_vals)
            (site_dir / "vars.yml").write_text(content)
            st.success(f"Wrote {site_dir / 'vars.yml'}")
        if vars_exists:
            st.caption("vars.yml exists ✓")

    with f2:
        vault_exists = site_dir is not None and (site_dir / "vars.vault.yml").exists()
        secrets_ok = st.session_state.get("pi_password") and st.session_state.get("vpn_password")
        if st.button("Write vars.vault.yml (encrypted)", key="btn_vault",
                     disabled=not (ready and secrets_ok) or (vault_exists and not overwrite)):
            site_dir.mkdir(parents=True, exist_ok=True)
            content = build_vault_yml({
                "pi_password": st.session_state["pi_password"],
                "vpn_password": st.session_state["vpn_password"],
                "cam_user": st.session_state["cam_user"],
                "cam_pwd": st.session_state["cam_pwd"],
                "wifi_ssid": st.session_state["wifi_ssid"],
                "wifi_password": st.session_state["wifi_password"],
            })
            vpf = root_env.get("VAULT_PASSWORD_FILE")
            vpf_path = resolve_path(vpf) if vpf else None
            try:
                encrypted = encrypt_vault(site_dir / "vars.vault.yml", content, vpf_path)
                if encrypted:
                    st.success(f"Wrote and encrypted {site_dir / 'vars.vault.yml'}")
                else:
                    st.warning(
                        f"Wrote {site_dir / 'vars.vault.yml'} in PLAINTEXT "
                        "(ansible-vault or VAULT_PASSWORD_FILE unavailable). Encrypt it with:\n\n"
                        f"`ansible-vault encrypt {site_dir / 'vars.vault.yml'} "
                        f"--vault-password-file {vpf or '<vault password file>'}`"
                    )
            except RuntimeError as exc:
                st.error(str(exc))
        if not secrets_ok:
            st.caption("Fill Pi + VPN passwords first")
        if vault_exists:
            st.caption("vars.vault.yml exists ✓")

    with f3:
        if st.button("Update hosts_prod", key="btn_inv", disabled=not (ready and st.session_state.get("pi_local_ip"))):
            group = None
            if st.session_state["group_choice"] == NEW_GROUP:
                group = st.session_state.get("new_group", "").strip() or None
            elif st.session_state["group_choice"] != NO_GROUP:
                group = st.session_state["group_choice"]
            try:
                changes = update_hosts_prod(
                    inv_path, site, st.session_state["pi_local_ip"],
                    int(st.session_state["ssh_port"]), group,
                )
                if changes:
                    st.success(f"hosts_prod updated: {', '.join(changes)}")
                else:
                    st.info("hosts_prod already up to date")
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))

    # ---- 6. launch
    st.header("6. Launch init-one-engine")
    st.caption("Runs `make init-one-engine SITE=<site>` inside the pyro-ansible container.")
    container_up = False
    if shutil.which("docker"):
        probe = subprocess.run(
            ["docker", "ps", "--filter", "name=pyro-ansible", "--format", "{{.Names}}"],
            capture_output=True, text=True,
        )
        container_up = "pyro-ansible" in probe.stdout
    if not container_up:
        st.warning("pyro-ansible container is not running. Start it first:")
        st.code("make ansible-up", language="bash")
        st.code(f"make init-one-engine SITE={site or '<site>'}", language="bash")
    elif st.button("Run init-one-engine", key="btn_run", type="primary", disabled=not site):
        cmd = ["docker", "exec", "pyro-ansible", "make", "init-one-engine", f"SITE={site}"]
        st.write(f"Running: `{' '.join(cmd)}`")
        box = st.empty()
        lines = []
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            lines.append(line.rstrip())
            box.code("\n".join(lines[-40:]))
        proc.wait()
        if proc.returncode == 0:
            st.success("init-one-engine finished successfully")
        else:
            st.error(f"init-one-engine failed (exit {proc.returncode}) — full output above")

    # ---- sidebar progress (filesystem-based, survives restarts)
    st.sidebar.divider()
    st.sidebar.subheader("Progress")
    if site:
        cam_ok = bool(cam_results) and not missing_ids
        checks = [
            ("Cameras created in API", cam_ok),
            ("vars.yml written", site_dir is not None and (site_dir / "vars.yml").exists()),
            ("vars.vault.yml written", site_dir is not None and (site_dir / "vars.vault.yml").exists()),
        ]
        if inv_path.exists():
            inv_hosts = yaml.safe_load(inv_path.read_text())["all"].get("hosts") or {}
            checks.append(("host in hosts_prod", site in inv_hosts))
        for label, done in checks:
            st.sidebar.write(("✅ " if done else "⬜ ") + label)
    else:
        st.sidebar.caption("Set a site name to track progress")

    save_draft()


if __name__ == "__main__":
    main()
