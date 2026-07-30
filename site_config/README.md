# Station Setup App

Streamlit app that takes a new engine site from zero to `make init-one-engine`:

1. **Environment** — sister repo path (`pi-manager-X`), API credentials read from `init_script/.env`.
2. **Site** — name, number of cameras, location (`lat,lon`), elevation, angle of view, per-camera IP/adapter, poses.
3. **Alert API** — create organization, optional user, and cameras + poses; returned camera ids and pose ids are captured automatically into `config_json`.
4. **Secrets** — Pi password (`ansible_password`), VPN password, camera and wifi credentials.
5. **Host files** — writes `host_vars/<site>/vars.yml`, writes and encrypts `vars.vault.yml` (via `ansible-vault` and `VAULT_PASSWORD_FILE` from the root `.env`), and adds the host to `inventory/hosts_prod` (host entry + `engine_servers` + optional site group, `reverse_ssh_port` auto-allocated).
6. **Init** — shows the commands to run yourself (`make ansible-up`, then `make init-one-engine SITE=<site>`); the app never runs ansible.
7. **VPN switch** — after init, detects the Pi's VPN address (`192.168.255.x` on `tun0`) and updates `ansible_host` in `hosts_prod` so future deploys go through the VPN.
8. **Deploy** — shows the `make deploy-one-engine SITE=<site>` command to run once `ansible_host` is on the VPN.

## Usage

```bash
uv run --with streamlit,pyyaml,requests streamlit run site_config/app.py
```

Then open http://localhost:8501 in your browser.

## Default secrets from `.env`

The camera and wifi passwords are usually the same across sites. You can store
them once in the root `.env` (see `.env.template`) and the app will pre-fill the
matching fields in step 4:

```bash
CAM_PWD=<camera password>
WIFI_PASSWORD=<wifi password>
```

Both are optional — when absent or empty, the fields simply start empty and must
be typed in the UI. Like all secrets they are never written to drafts.

## Drafts

Every non-secret input and API result is auto-saved to `site_config/drafts/<site>.json`
(gitignored), so a Streamlit restart loses nothing: pick the site in the sidebar
"Resume a draft" selector. Secrets are kept in memory only and must be re-entered
after a restart.
