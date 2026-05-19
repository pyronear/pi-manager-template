import os
import pandas as pd
from common import get_token, api_request, get_organization_id
from dotenv import load_dotenv

load_dotenv(override=True)

api_url = os.getenv("API_URL")
superuser_login = os.getenv("SUPERADMIN_LOGIN")
superuser_pwd = os.getenv("SUPERADMIN_PWD")
organization_name = os.getenv("organization_name")

superuser_auth = {
    "Authorization": f"Bearer {get_token(api_url, superuser_login, superuser_pwd)}",
    "Content-Type": "application/json",
}

cameras_csv = pd.read_csv("cameras.csv")
cameras_csv = cameras_csv.fillna(0)

organization_id = get_organization_id(api_url, superuser_auth, organization_name)

# Fetch existing cameras to avoid duplicates
existing = api_request("get", f"{api_url}/api/v1/cameras/?include_non_trustable=true", superuser_auth)
existing_names = {c["name"] for c in existing if c["organization_id"] == organization_id}


def compute_azimuths(cam_index: int, total_ptz_cams: int, n_poses: int) -> list:
    """Evenly distribute azimuths across all PTZ cameras at the site."""
    total_positions = total_ptz_cams * n_poses
    step = 360 / total_positions
    start = cam_index * n_poses
    return [round(step * (start + j)) % 360 for j in range(n_poses)]


# Count PTZ cameras (n_poses > 0) for azimuth distribution
ptz_rows = [c for c in cameras_csv.itertuples(index=False) if int(c.n_poses) > 0]
total_ptz = len(ptz_rows)

ptz_index = 0
for camera in cameras_csv.itertuples(index=False):
    n_poses = int(camera.n_poses)

    if camera.name in existing_names:
        print(f"Camera '{camera.name}' already exists, skipping.")
        if n_poses > 0:
            ptz_index += 1
        continue

    payload = {
        "organization_id": organization_id,
        "name": camera.name,
        "angle_of_view": camera.angle_of_view,
        "elevation": camera.elevation,
        "lat": camera.lat,
        "lon": camera.lon,
        "is_trustable": bool(camera.is_trustable),
    }
    response = api_request("post", f"{api_url}/api/v1/cameras/", superuser_auth, payload)
    camera_id = response["id"]
    print(f"Camera '{camera.name}' created with id: {camera_id}")

    if n_poses > 0:
        azimuths = compute_azimuths(ptz_index, total_ptz, n_poses)
        pose_ids = []
        for patrol_id, azimuth in enumerate(azimuths):
            pose_payload = {
                "camera_id": camera_id,
                "azimuth": azimuth,
                "patrol_id": patrol_id,
            }
            pose_resp = api_request("post", f"{api_url}/api/v1/poses/", superuser_auth, pose_payload)
            pose_ids.append(pose_resp["id"])
        print(f"  -> {n_poses} poses created | pose_ids: {pose_ids} | patrol_ids: {list(range(n_poses))}")
        ptz_index += 1
