# Station Setup App

Streamlit app that takes a new engine site from zero to `make init-one-engine`:

1. **Environment** — sister repo path (`pi-manager-X`), API credentials read from `init_script/.env`.
2. **Site** — name, number of cameras, location (`lat,lon`), elevation, angle of view, per-camera IP/adapter, poses.
3. **Alert API** — create organization, optional user, and cameras + poses; returned camera ids and pose ids are captured automatically into `config_json`.
4. **Secrets** — Pi password (`ansible_password`), VPN password, camera and wifi credentials.
5. **Host files** — writes `host_vars/<site>/vars.yml`, writes and encrypts `vars.vault.yml` (via `ansible-vault` and `VAULT_PASSWORD_FILE` from the root `.env`), and adds the host to `inventory/hosts_prod` (host entry + `engine_servers` + optional site group, `reverse_ssh_port` auto-allocated).
6. **Launch** — runs `make init-one-engine SITE=<site>` inside the running `pyro-ansible` container with live output.
7. **VPN switch** — after init, detects the Pi's VPN address (`192.168.255.x` on `tun0`) and updates `ansible_host` in `hosts_prod` so future deploys go through the VPN.

## Usage

```bash
uv run --with streamlit,pyyaml,requests streamlit run site_config/app.py
```

Then open http://localhost:8501 in your browser.

## Drafts

Every non-secret input and API result is auto-saved to `site_config/drafts/<site>.json`
(gitignored), so a Streamlit restart loses nothing: pick the site in the sidebar
"Resume a draft" selector. Secrets are kept in memory only and must be re-entered
after a restart.
