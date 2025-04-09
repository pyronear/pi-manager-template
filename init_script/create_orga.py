import os
import pandas as pd
from common import get_token, api_request
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv(override=True)

api_url = os.getenv("API_URL")
superuser_login = os.getenv("SUPERADMIN_LOGIN")
superuser_pwd = os.getenv("SUPERADMIN_PWD")

organization_name  = os.getenv("organization_name")

superuser_auth = {
    "Authorization": f"Bearer {get_token(api_url, superuser_login, superuser_pwd)}",
    "Content-Type": "application/json",
}

# Créer les organisations
payload = {"name": organization_name}
response = api_request("post", f"{api_url}/api/v1/organizations/", superuser_auth, payload)
print(f"Organisation '{organization_name}' créée avec succès.")
