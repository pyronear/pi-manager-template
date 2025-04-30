import os
import pandas as pd
from common import get_token, api_request, get_organization_id
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv(override=True)

api_url = os.getenv("API_URL")
superuser_login = os.getenv("SUPERADMIN_LOGIN")
superuser_pwd = os.getenv("SUPERADMIN_PWD")

organization_name = os.getenv("organization_name")

print(api_url)

superuser_auth = {
    "Authorization": f"Bearer {get_token(api_url, superuser_login, superuser_pwd)}",
    "Content-Type": "application/json",
}

cameras = pd.read_csv(f"cameras.csv")
cameras = cameras.fillna("")


organization_id = get_organization_id(api_url, superuser_auth, organization_name)

# Créer les caméras
for camera in cameras.itertuples(index=False):
    payload = {
        "organization_id": organization_id,
        "name": camera.name,
        "angle_of_view": camera.angle_of_view,
        "elevation": camera.elevation,
        "lat": camera.lat,
        "lon": camera.lon,
        "is_trustable": camera.is_trustable,
    }
    response = api_request("post", f"{api_url}/api/v1/cameras/", superuser_auth, payload)
    camera_id = response["id"]
    print(f"Camera '{camera.name}' créée avec succès avec l'id : '{camera_id}'.")
