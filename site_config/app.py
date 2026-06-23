import json
import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Make init_script importable so we reuse the API helpers instead of shelling out.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "init_script"))

from common import (  # noqa: E402
    create_camera,
    create_pose,
    ensure_organization_id,
    get_cameras,
    get_poses,
    get_token,
)

# Repo-level config (REPO_PATH, VAULT_PASSWORD_FILE) lives in the root .env.
# init_script/.env optionally prefills the API_URL / superadmin fields.
load_dotenv(REPO_ROOT / ".env", override=True)
load_dotenv(REPO_ROOT / "init_script" / ".env", override=False)

REPO_PATH = os.getenv("REPO_PATH")
VAULT_PASSWORD_FILE = os.getenv("VAULT_PASSWORD_FILE")

ADAPTERS = [
    "reolink-823S2",
    "reolink-823A16",
    "reolink-810a",
    "reolink-duo2",
    "reolink-915A?",
    "linovision",
    "url",
]

# Static-IP / wifi defaults (not collected in the form, see plan).
STATIC_IP_INTERFACE = "eth0"
STATIC_IP_ADDRESS = "192.168.1.99"
STATIC_IP_GATEWAY = "192.168.1.1"
DEFAULT_WIFI_SSID = "Pyronear"
DEFAULT_WIFI_PASSWORD = "@Pyronear"


def compute_azimuths(cam_index: int, num_cams: int, n_poses: int) -> list[int]:
    """Evenly spaced azimuths for a camera, split across all cameras."""
    total_positions = num_cams * n_poses
    step = 360 / total_positions
    start = cam_index * n_poses
    return [round(step * (start + j)) % 360 for j in range(n_poses)]


def parse_coords(text: str) -> tuple[float, float]:
    """Parse a 'lat,lon' string into floats, raising ValueError if malformed."""
    lat_str, lon_str = text.split(",")
    return float(lat_str), float(lon_str)


def resolve_vault_password_file() -> Path | None:
    if not VAULT_PASSWORD_FILE:
        return None
    path = Path(VAULT_PASSWORD_FILE)
    return path if path.is_absolute() else (REPO_ROOT / path)


def build_vars_yml(config_dict: dict, watchdog_type: str) -> str:
    json_str = json.dumps(config_dict, indent=4, ensure_ascii=False)
    indented = "\n".join("    " + line for line in json_str.splitlines())
    lines = [
        f"config_json: |\n{indented}",
        "",
        f"static_ip_interface: {STATIC_IP_INTERFACE}",
        f"static_ip_address: {STATIC_IP_ADDRESS}",
        f"static_ip_gateway: {STATIC_IP_GATEWAY}",
    ]
    if watchdog_type:
        lines += ["", f"watchdog_type: {watchdog_type}"]
    return "\n".join(lines) + "\n"


def build_vault_yml(ansible_password: str, cam_user: str, cam_pwd: str, openvpn_password: str) -> str:
    # json.dumps produces a valid double-quoted YAML scalar with proper escaping.
    return (
        f"ansible_password: {json.dumps(ansible_password)}\n"
        'ansible_become_password: "{{ ansible_password }}"\n'
        "\n"
        "##### ENGINE\n"
        f"CAM_USER: {json.dumps(cam_user)}\n"
        f"CAM_PWD: {json.dumps(cam_pwd)}\n"
        f"open_vpn_password: {json.dumps(openvpn_password)}\n"
        "## VPN\n"
        'openvpn_client_password: "{{ open_vpn_password }}"\n'
        "\n"
        "\n"
        "wifi_connections:\n"
        f"  - ssid: {json.dumps(DEFAULT_WIFI_SSID)}\n"
        f"    password: {json.dumps(DEFAULT_WIFI_PASSWORD)}\n"
        "    priority: 10\n"
    )


def encrypt_vault_file(path: Path, vault_password_file: Path) -> None:
    subprocess.run(
        [
            "ansible-vault",
            "encrypt",
            str(path),
            "--vault-password-file",
            str(vault_password_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def provision_and_write(form: dict) -> Path:
    """Create org/cameras/poses via the API, then write the host_vars folder."""
    headers = {
        "Authorization": f"Bearer {get_token(form['api_url'], form['su_login'], form['su_pwd'])}",
        "Content-Type": "application/json",
    }
    org_id = ensure_organization_id(form["api_url"], headers, form["org_name"])

    existing_cams = get_cameras(form["api_url"], headers)
    existing_poses = get_poses(form["api_url"], headers)

    config_dict = {}
    num_cams = len(form["cameras"])
    for i, cam in enumerate(form["cameras"]):
        match = next(
            (c for c in existing_cams if c["organization_id"] == org_id and c["name"] == cam["name"]),
            None,
        )
        if match:
            cam_id = match["id"]
        else:
            created = create_camera(
                form["api_url"],
                headers,
                {
                    "organization_id": org_id,
                    "name": cam["name"],
                    "angle_of_view": cam["angle_of_view"],
                    "elevation": cam["elevation"],
                    "lat": cam["lat"],
                    "lon": cam["lon"],
                    "is_trustable": cam["is_trustable"],
                },
            )
            cam_id = created["id"]

        ordered: dict = {}
        if cam["type"] == "ptz":
            n_poses = cam["n_poses"]
            azimuths = compute_azimuths(i, num_cams, n_poses)
            pose_ids = []
            for patrol_id, azimuth in enumerate(azimuths):
                existing = next(
                    (p for p in existing_poses if p["camera_id"] == cam_id and p["patrol_id"] == patrol_id),
                    None,
                )
                if existing:
                    pose_ids.append(existing["id"])
                else:
                    pose = create_pose(
                        form["api_url"],
                        headers,
                        {"camera_id": cam_id, "azimuth": azimuth, "patrol_id": patrol_id},
                    )
                    pose_ids.append(pose["id"])
            ordered["pose_ids"] = pose_ids
        else:
            ordered["azimuth"] = cam["azimuth"]

        ordered["adapter"] = cam["adapter"]
        if cam.get("anonymizer"):
            ordered["anonymizer"] = True
        ordered["id"] = str(cam_id)
        ordered["name"] = cam["name"]
        ordered["bbox_mask_url"] = ""
        ordered["poses"] = list(range(cam["n_poses"])) if cam["type"] == "ptz" else []
        ordered["token"] = ""
        ordered["type"] = cam["type"]
        config_dict[cam["ip"]] = ordered

    assert REPO_PATH, "REPO_PATH must be set"
    dest = Path(REPO_PATH) / "host_vars" / form["site_name"]
    dest.mkdir(parents=True, exist_ok=True)

    (dest / "vars.yml").write_text(build_vars_yml(config_dict, form["watchdog_type"]))

    vault_path = dest / "vars.vault.yml"
    vault_path.write_text(
        build_vault_yml(form["ansible_password"], form["cam_user"], form["cam_pwd"], form["open_vpn_password"])
    )
    try:
        encrypt_vault_file(vault_path, form["vault_password_file"])
    except Exception:
        # Never leave plaintext secrets on disk if encryption fails.
        vault_path.unlink(missing_ok=True)
        raise

    return dest


def main():
    st.set_page_config(page_title="Pyronear Site Config Generator", layout="wide")
    st.title("Pyronear Site Config Generator")

    if not REPO_PATH:
        st.error("REPO_PATH is not set in the repo-root .env — cannot write host_vars.")
        st.stop()

    vault_password_file = resolve_vault_password_file()
    if vault_password_file is None or not vault_password_file.exists():
        st.error("VAULT_PASSWORD_FILE is not set or missing — cannot encrypt vars.vault.yml.")
        st.stop()

    # --- Site-level settings ---
    col1, col2 = st.columns(2)
    with col1:
        site_name = st.text_input("Site name", placeholder="sdis-tigery")
    with col2:
        num_cams = st.number_input("Number of cameras", min_value=1, max_value=20, value=2)

    c1, c2, c3 = st.columns(3)
    with c1:
        cam_type = st.radio("Camera type", ["ptz", "static"], horizontal=True)
    with c2:
        watchdog_type = st.text_input("Watchdog type", value="shelly")
    with c3:
        coords = st.text_input("Coordinates (lat,lon)", placeholder="48.1234,2.5678")

    # --- API access ---
    st.subheader("API access")
    a1, a2, a3 = st.columns(3)
    with a1:
        api_url = st.text_input("API URL", value=os.getenv("API_URL", "https://alertapi.pyronear.org/"))
    with a2:
        su_login = st.text_input("Superadmin login", value=os.getenv("SUPERADMIN_LOGIN", ""))
    with a3:
        su_pwd = st.text_input("Superadmin password", value=os.getenv("SUPERADMIN_PWD", ""), type="password")
    org_name = st.text_input("Organization name", value=site_name)

    # --- Vault secrets ---
    st.subheader("Secrets (written to vars.vault.yml)")
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        ansible_password = st.text_input("ansible_password", type="password")
    with v2:
        open_vpn_password = st.text_input("open_vpn_password", type="password")
    with v3:
        cam_user = st.text_input("CAM_USER", value="admin")
    with v4:
        cam_pwd = st.text_input("CAM_PWD", value="@Pyronear", type="password")

    st.divider()

    # --- Per-camera settings ---
    cameras: list[dict] = []
    for i in range(num_cams):
        st.subheader(f"Camera {i + 1}")
        name = f"{site_name}-{i + 1:02d}" if site_name else ""

        c1, c2, c3 = st.columns(3)
        with c1:
            ip = st.text_input("IP address", value=f"192.168.1.{11 + i}", key=f"ip_{i}")
        with c2:
            adapter = st.selectbox("Adapter", ADAPTERS + ["Other..."], key=f"adapter_{i}")
            if adapter == "Other...":
                adapter = st.text_input("Custom adapter", key=f"adapter_custom_{i}")
        with c3:
            anonymizer = st.checkbox("Anonymizer", value=False, key=f"anon_{i}")

        g1, g2, g3 = st.columns(3)
        with g1:
            elevation = st.number_input("Elevation (m)", value=100, key=f"elev_{i}")
        with g2:
            angle_of_view = st.number_input("Angle of view", value=54.2, format="%.1f", key=f"aov_{i}")
        with g3:
            is_trustable = st.checkbox("Trustable", value=True, key=f"trust_{i}")

        cam: dict = {
            "ip": ip,
            "name": name,
            "adapter": adapter,
            "anonymizer": anonymizer,
            "type": cam_type,
            "elevation": elevation,
            "angle_of_view": angle_of_view,
            "is_trustable": is_trustable,
            "n_poses": 0,
        }
        if cam_type == "ptz":
            cam["n_poses"] = st.number_input(
                "Number of poses", min_value=1, max_value=12, value=4, key=f"nposes_{i}"
            )
        else:
            cam["azimuth"] = round(i * 360 / num_cams) % 360
        cameras.append(cam)

    st.divider()

    if st.button("Generate site", type="primary"):
        missing = [
            label
            for label, value in [
                ("Site name", site_name),
                ("API URL", api_url),
                ("Superadmin login", su_login),
                ("Superadmin password", su_pwd),
                ("ansible_password", ansible_password),
                ("open_vpn_password", open_vpn_password),
            ]
            if not value
        ]
        if missing:
            st.error("Missing required fields: " + ", ".join(missing))
            st.stop()

        if not re.fullmatch(r"[a-z0-9-]+", site_name):
            st.error("Site name must contain only lowercase letters, digits and hyphens.")
            st.stop()

        ips = [c["ip"] for c in cameras]
        if any(not ip for ip in ips) or len(set(ips)) != len(ips):
            st.error("Camera IP addresses must all be set and unique.")
            st.stop()

        try:
            lat, lon = parse_coords(coords)
        except ValueError:
            st.error("Coordinates must be in 'lat,lon' format (e.g. 48.1234,2.5678).")
            st.stop()
            return
        for cam in cameras:
            cam["lat"], cam["lon"] = lat, lon

        form = {
            "site_name": site_name,
            "watchdog_type": watchdog_type,
            "api_url": api_url.rstrip("/"),
            "su_login": su_login,
            "su_pwd": su_pwd,
            "org_name": org_name or site_name,
            "ansible_password": ansible_password,
            "open_vpn_password": open_vpn_password,
            "cam_user": cam_user,
            "cam_pwd": cam_pwd,
            "vault_password_file": vault_password_file,
            "cameras": cameras,
        }

        try:
            with st.spinner("Creating org/cameras/poses and writing host_vars..."):
                dest = provision_and_write(form)
        except subprocess.CalledProcessError as exc:
            st.error(f"ansible-vault encrypt failed:\n{exc.stderr or exc.stdout}")
        except Exception as exc:  # surface API/file errors in the UI
            st.error(f"Generation failed: {exc}")
        else:
            st.success(f"Site written to {dest}")
            st.code((dest / "vars.yml").read_text(), language="yaml")


if __name__ == "__main__":
    main()
