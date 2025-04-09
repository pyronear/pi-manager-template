import os
import pandas as pd
from common import get_token, api_request, get_organization_id
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv(override=True)

api_url = os.getenv("API_URL")
superuser_login = os.getenv("SUPERADMIN_LOGIN")
superuser_pwd = os.getenv("SUPERADMIN_PWD")

login = os.getenv("api_login")
pwd = os.getenv("api_pwd")
role = os.getenv("role")
organization_name = os.getenv("organization_name")

superuser_auth = {
    "Authorization": f"Bearer {get_token(api_url, superuser_login, superuser_pwd)}",
    "Content-Type": "application/json",
}

# Créer un utilisateur
organization_id = get_organization_id(api_url, superuser_auth, organization_name)
payload = {
    "organization_id": organization_id,
    "password": pwd,
    "login": login,
    "role": role,
}
api_request("post", f"{api_url}/api/v1/users/", superuser_auth, payload)
print(f"Utilisateur '{login}' créé avec succès.")
