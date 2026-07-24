# Watchdog Setup

Watchdog scripts monitor hardware health and power-cycle relays on failure.
All are managed by Ansible and read their configuration from a `.env` file generated on the device.

A site uses **one** variant, selected by the `watchdog_type` host var
(`no_watchdog`, `pi_zero` or `shelly`, defaults to `no_watchdog` in group_vars):
- **`no_watchdog`** — nightly reboot cron only.
- **`pi_zero`** — the engine and a Pi Zero watchdog each other through power relays. Also requires `pi_zero_hostname`.
- **`shelly`** — a Shelly Pro smart relay watches the engine, and the engine asks the Shelly to power-cycle the cameras/router.

All watchdog scripts live in the [pyro-engine](https://github.com/pyronear/pyro-engine) repo (`watchdog/`), which requires `pyro_engine_git_ref` >= `v1.0.12`.

---

## Overview

| Script | Runs on | Monitors | Cron schedule |
|--------|---------|----------|---------------|
| `watchdog/zero/main_pi/watchdog.py` | Engine (`/home/pyro-engine/`) | Pi Zero reachability | `5,15,25,35,45,55 * * * *` |
| `watchdog/zero/pi_zero/watchdog.py` | Pi Zero | Engine health + camera pings | `*/10 * * * *` |
| `watchdog/shelly/main_pi/watchdog.py` | Engine (`/home/pyro-engine/`) | Internet + camera pings | `5,15,25,35,45,55 * * * *` |
| `watchdog.js` (Shelly script) | Shelly device | Engine health endpoint | every 10 min |

The paired schedules are offset by 5 minutes so they never run simultaneously.

---

## Engine watchdog (`main_pi`)

Pings the Pi Zero. If unreachable after `MAX_FAILS` attempts, power-cycles the Pi Zero relay.

Deployed by the `engine_cron` role, called from `deploy-engines.yml`.

Only runs if `watchdog_type: pi_zero` is set in the engine's host_vars.

| Variable | Where | Description |
|----------|-------|-------------|
| `watchdog_type` | `host_vars/<engine>/vars.yml` | `pi_zero` for this variant |
| `pi_zero_hostname` | `host_vars/<engine>/vars.yml` | Inventory hostname of the associated Pi Zero (e.g. `chambery-pi-zero`). Leave empty if no Pi Zero. |

`PIZERO_IP` is derived automatically from `hostvars[pi_zero_hostname]['static_ip_address']` — no manual configuration needed.

---

## Pi Zero watchdog (`pi_zero`)

Checks the engine's health endpoint and pings all cameras. Power-cycles relays on repeated failures.

Deployed by the `pi_zero_watchdog` role, called from `rpi-init-pi-zero.yml`.

| Variable | Where | Description |
|----------|-------|-------------|
| `pi_zero_hostname` | `host_vars/<pi-zero>/vars.yml` | Not required here — see relay_host |
| `relay_host` | `host_vars/<pi-zero>/vars.yml` | Inventory hostname of the associated engine |

`MAIN_PI_IP` is derived from `hostvars[relay_host]['static_ip_address']`.
`CAM_IPS` is derived from the keys of `hostvars[relay_host]['config_json']`.

---

## Shelly watchdog

For sites where the engine is paired with a Shelly Pro relay instead of a Pi Zero.
Enabled with `watchdog_type: shelly` in the engine's host_vars (mutually
exclusive with `pi_zero_hostname`).

The two sides are deployed by two roles, both called from `deploy-engines.yml`:

- **Engine side** (`engine_cron` role) — writes `/home/pi/watchdog.env` (`SHELLY_IP`,
  `SHELLY_OUTPUT_ID`, `CAM_IPS` from the keys of the host's `config_json`) and a cron
  entry for `watchdog/shelly/main_pi/watchdog.py`, which checks internet + cameras and
  asks the Shelly to power-cycle output 0 on repeated failures.
- **Shelly side** (`shelly_watchdog` role) — from the engine (which shares the Shelly's LAN), runs the
  upstream `harden_shelly.sh` (disables cloud/MQTT/BLE/AP, forces outputs on at
  boot) and uploads `watchdog.js` with `PI_URL` patched to the engine's
  `http://<static_ip_address>:8081/health` endpoint. The Shelly then reboots the
  engine's power if the health endpoint fails repeatedly. The play verifies the
  script reports `running: true` at the end.

The upload is skipped when the patched `watchdog.js` is unchanged and the script
is already running, so a routine re-deploy does not reset the Shelly's reboot budget.

| Variable | Where | Description |
|----------|-------|-------------|
| `watchdog_type` | `host_vars/<engine>/vars.yml` | `shelly` for this variant |
| `shelly_ip` | role default | Shelly's fixed LAN IP (`192.168.1.97`, same on every site) |
| `shelly_output_id` | role default | Shelly output power-cycled by the engine (`0`) |

**Prerequisite (manual, once per device):** put the Shelly on the site's Wi-Fi at
its fixed IP with the Shelly Smart Control app (Bluetooth onboarding). See
`watchdog/shelly/device/README.md` in pyro-engine. Make sure the Shelly is not
powered by one of the outputs it cuts.

---

## Summary of variables per new engine + Pi Zero pair

### Engine — `host_vars/<engine>/vars.yml`
```yaml
watchdog_type: pi_zero
pi_zero_hostname: <pi-zero-inventory-name>   # e.g. chambery-pi-zero
static_ip_address: 192.168.X.Y
static_ip_gateway: 192.168.X.1
static_ip_interface: eth0
```

### Pi Zero — `host_vars/<pi-zero>/vars.yml`
```yaml
ansible_host: 192.168.X.Z       # DHCP ip on first run, then static after init
relay_host: <engine-hostname>   # e.g. engine-chambery
wifi_ssid: "<network>"
static_ip_address: 192.168.X.Z
static_ip_gateway: 192.168.X.1
```

### Pi Zero — `host_vars/<pi-zero>/vars.vault.yml`
```yaml
ansible_password: "<pi-zero-password>"
wifi_password: "<wifi-password>"
```

---

## After first init (`rpi-init-pi-zero.yml`)

The Pi Zero reboots with its static IP. Update `ansible_host` in host_vars to `static_ip_address` before any subsequent run.
