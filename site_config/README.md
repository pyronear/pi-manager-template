# Site Config Generator

Streamlit app that provisions a new Pyronear site end-to-end: it creates the
organization, cameras and poses in the alert API, then writes the encrypted
`host_vars/<site>/` folder into the sister repo (`$REPO_PATH`).

## Usage

```bash
uv run --with streamlit --with requests --with pandas --with python-dotenv \
  streamlit run site_config/app.py
```

Then open http://localhost:8501 in your browser.

It reads `REPO_PATH` and `VAULT_PASSWORD_FILE` from the repo-root `.env`, and
optionally prefills `API_URL` / superadmin credentials from `init_script/.env`.

## What "Generate site" does

1. Logs into the API with the superadmin credentials.
2. Ensures the organization exists (created if missing).
3. For each camera: creates it (or reuses an existing one with the same name),
   then creates its poses, capturing the returned `id` and `pose_ids`.
4. Writes `$REPO_PATH/host_vars/<site>/vars.yml` — `config_json` (with `id` and
   `pose_ids` embedded), static-IP defaults and `watchdog_type`.
5. Writes `$REPO_PATH/host_vars/<site>/vars.vault.yml` with the secrets, then
   runs `ansible-vault encrypt` using `VAULT_PASSWORD_FILE`.

The API step is idempotent: re-running reuses existing cameras/poses by name.

## Fields

- Site name, number of cameras, camera type (PTZ or static), watchdog type
- API URL + superadmin credentials, organization name
- Secrets written to the vault file: `ansible_password`, `open_vpn_password`,
  `CAM_USER`, `CAM_PWD`
- Per camera: IP, adapter, anonymizer, and the geo data needed to create it in
  the API (latitude, longitude, elevation, angle of view, trustable, poses)

Static IP (`.99`/`.1`/`eth0`) and the WiFi block default to standard values and
are not collected in the form — edit `vars.yml` / `vars.vault.yml` afterwards if
a site needs different ones.
