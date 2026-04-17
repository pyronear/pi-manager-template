# Watchdog Setup

Two watchdog scripts monitor hardware health and power-cycle relays on failure.
Both are managed by Ansible and read their configuration from a `.env` file generated on the device.

---

## Overview

| Script | Runs on | Monitors | Cron schedule |
|--------|---------|----------|---------------|
| `watchdog/main_pi/watchdog.py` | Engine (`/home/pyro-engine/`) | Pi Zero reachability | `5,15,25,35,45,55 * * * *` |
| `watchdog/pi_zero/watchdog.py` | Pi Zero | Engine health + camera pings | `*/10 * * * *` |

The two schedules are offset by 5 minutes so they never run simultaneously.

---

## Engine watchdog (`main_pi`)

Pings the Pi Zero. If unreachable after `MAX_FAILS` attempts, power-cycles the Pi Zero relay.

Deployed by the `engine_cron` role, called from `deploy-engines.yml`.

Only runs if `pi_zero_hostname` is set in the engine's host_vars.

| Variable | Where | Description |
|----------|-------|-------------|
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

## Summary of variables per new engine + Pi Zero pair

### Engine — `host_vars/<engine>/vars.yml`
```yaml
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
