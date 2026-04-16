import json
import streamlit as st

ADAPTERS = [
    "reolink-823S2",
    "reolink-823A16",
    "reolink-810a",
    "reolink-duo2",
    "reolink-915A?",
    "linovision",
    "url",
]

MASK_URL_BASE = "https://occlusion-masks-json.s3.sbg.io.cloud.ovh.net"


def compute_azimuths(cam_index: int, num_cams: int, n_poses: int) -> list[int]:
    """Evenly spaced azimuths for a camera, split across all cameras."""
    total_positions = num_cams * n_poses
    step = 360 / total_positions
    start = cam_index * n_poses
    return [round(step * (start + j)) % 360 for j in range(n_poses)]


def main():
    st.set_page_config(page_title="Pyronear Site Config Generator", layout="wide")
    st.title("Pyronear Site Config Generator")

    # --- Site-level settings ---
    col1, col2 = st.columns(2)
    with col1:
        site_name = st.text_input("Site name", placeholder="germersheim")
    with col2:
        num_cams = st.number_input("Number of cameras", min_value=1, max_value=20, value=2)

    cam_type = st.radio("Camera type", ["ptz", "static"], horizontal=True)

    st.divider()

    # --- Per-camera settings ---
    cameras: list[dict] = []
    for i in range(num_cams):
        st.subheader(f"Camera {i + 1}")
        c1, c2, c3 = st.columns(3)

        with c1:
            ip = st.text_input("IP address", value=f"192.168.1.{11 + i}", key=f"ip_{i}")
        with c2:
            cam_id = st.text_input("Camera ID (from API)", value="", key=f"id_{i}")
        with c3:
            adapter = st.selectbox("Adapter", ADAPTERS + ["Other..."], key=f"adapter_{i}")
            if adapter == "Other...":
                adapter = st.text_input("Custom adapter", key=f"adapter_custom_{i}")

        name = f"{site_name}-{i + 1:02d}" if site_name else ""

        if cam_type == "ptz":
            n_poses = st.number_input(
                "Number of poses", min_value=1, max_value=12, value=4, key=f"nposes_{i}"
            )
            azimuths = compute_azimuths(i, num_cams, n_poses)
            poses = list(range(n_poses))
        else:
            azimuth_val = round(i * 360 / num_cams) % 360
            azimuths = None
            poses = []

        anonymizer = st.checkbox("Anonymizer", value=False, key=f"anon_{i}")

        cam_data: dict = {
            "adapter": adapter,
            "id": cam_id,
            "name": name,
            "bbox_mask_url": f"{MASK_URL_BASE}/{site_name}" if site_name else "",
            "poses": poses,
            "token": "",
            "type": cam_type,
        }
        if cam_type == "ptz":
            cam_data["azimuths"] = azimuths
        else:
            cam_data["azimuth"] = azimuth_val

        if anonymizer:
            cam_data["anonymizer"] = True

        cameras.append((ip, cam_data))

    # --- Generate output ---
    st.divider()
    st.subheader("Generated `vars` file")

    config_dict = {}
    for ip, cam_data in cameras:
        # Build ordered dict to match existing file format
        ordered = {}
        if cam_type == "ptz":
            ordered["azimuths"] = cam_data["azimuths"]
        else:
            ordered["azimuth"] = cam_data["azimuth"]
        ordered["adapter"] = cam_data["adapter"]
        if cam_data.get("anonymizer"):
            ordered["anonymizer"] = True
        ordered["id"] = cam_data["id"]
        ordered["name"] = cam_data["name"]
        ordered["bbox_mask_url"] = cam_data["bbox_mask_url"]
        ordered["poses"] = cam_data["poses"]
        ordered["token"] = cam_data["token"]
        ordered["type"] = cam_data["type"]
        config_dict[ip] = ordered

    json_str = json.dumps(config_dict, indent=4, ensure_ascii=False)
    # Indent each line by 4 spaces for YAML block scalar
    indented = "\n".join("    " + line for line in json_str.splitlines())
    output = f"config_json: |\n{indented}\n"

    st.code(output, language="yaml")

    if site_name:
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "Download vars file",
                data=output,
                file_name="vars",
                mime="text/plain",
            )
        with dl2:
            st.download_button(
                "Download JSON",
                data=json_str,
                file_name=f"{site_name}.json",
                mime="application/json",
            )


if __name__ == "__main__":
    main()
