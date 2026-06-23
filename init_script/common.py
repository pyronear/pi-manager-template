import requests
import logging
import sys
from typing import Any, Dict, Optional

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")


def get_token(api_url: str, login: str, pwd: str) -> str:
    print(api_url, login, pwd)
    response = requests.post(
        f"{api_url}/api/v1/login/creds",
        data={"username": login, "password": pwd},
        timeout=5,
    )
    if response.status_code != 200:
        raise ValueError(response.text)
    return response.json()["access_token"]


def api_request(
    method_type: str,
    route: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
):
    kwargs = {"json": payload} if isinstance(payload, dict) else {}

    response = getattr(requests, method_type)(route, headers=headers, **kwargs)
    try:
        detail = response.json()
    except (requests.exceptions.JSONDecodeError, KeyError):
        detail = response.text
    assert response.status_code // 100 == 2, print(detail)
    return response.json()

# Récupérer l'organisation par son nom
def get_organization_id(api_url: str, superuser_auth: Dict[str, str], org_name: str):
    response = api_request("get", f"{api_url}/api/v1/organizations/", superuser_auth)
    for orga in response:
        if orga["name"] == org_name:
            return orga["id"]
    raise ValueError(f"Organization '{org_name}' not found.")


# Idempotent helpers reused by the Streamlit site generator -------------------

def ensure_organization_id(api_url: str, headers: Dict[str, str], org_name: str):
    """Return the org id, creating the organization if it does not exist yet."""
    response = api_request("get", f"{api_url}/api/v1/organizations/", headers)
    for orga in response:
        if orga["name"] == org_name:
            return orga["id"]
    created = api_request("post", f"{api_url}/api/v1/organizations/", headers, {"name": org_name})
    return created["id"]


def get_cameras(api_url: str, headers: Dict[str, str]):
    return api_request("get", f"{api_url}/api/v1/cameras/?include_non_trustable=true", headers)


def create_camera(api_url: str, headers: Dict[str, str], payload: Dict[str, Any]):
    return api_request("post", f"{api_url}/api/v1/cameras/", headers, payload)


def get_poses(api_url: str, headers: Dict[str, str]):
    return api_request("get", f"{api_url}/api/v1/poses/", headers)


def create_pose(api_url: str, headers: Dict[str, str], payload: Dict[str, Any]):
    return api_request("post", f"{api_url}/api/v1/poses/", headers, payload)
