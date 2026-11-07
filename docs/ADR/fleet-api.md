# Fleet API: one service to configure, version and deploy stations and servers

- **Status:** Proposed
- **Deciders:** Mateo
- **Date:** November 2026
- **Issue:** pyronear/pi-manager-template#109 (epic pyronear/roadmap#14)
- **Supersedes in part:** `Mender vs Ansible` (Ansible stays, but it is driven by the Fleet API)

## 1. Context

Today a deployment is: edit YAML in a private country repo (`pi-manager-fr`, `pi-manager-chile`), then run an Ansible playbook from a laptop inside the `pyro-ansible` container.

The same station is described in four places that drift apart:

```mermaid
flowchart LR
    subgraph today["Today: one station, four sources"]
        HV["host_vars<br/>config_json, image pins"]
        INV["inventory<br/>ansible_host (VPN IP)"]
        API["alert API<br/>cameras, poses"]
        DC["device_config<br/>patched by a script"]
    end
    HV -. drift .- API
    INV -. drift .- HV
    DC -. drift .- API
```

Incidents caused by this drift:

- a camera in `config_json` that does not exist in the API (snow-valley);
- inventory entries pointing at another site's Pi after the VPN renumbering;
- image pins in `host_vars` wiped by a `git reset`;
- `device_config` applied by hand.

Other problems:

- Nobody can tell which version runs on which station.
- Deployments are slow and manual.
- During fire season, server updates must not cut the service during the day.

## 2. Decision

We build a custom **Fleet API** (FastAPI + Postgres) with a small frontend and a worker that runs the existing Ansible roles.

| Topic | Decision |
|---|---|
| Source of truth | Read as much as possible from the **alert API** (cameras, poses, engine heartbeat). The Fleet API stores only what the alert API does not have. |
| Secrets | Stored **encrypted in the database**, with a key per instance (env var). Never returned in clear by the API or the frontend. |
| Security | Reachable through the VPN only, with authentication and an audit log of every action. |
| Instances | **One instance per country** (France, Chile, ...). Anyone can also run one **locally** with the same `docker compose`. |
| Execution | **Ansible stays.** The roles in this repo are embedded in the worker image. |
| Update model | **Push** to decide, **local execution** on the Pi (`pyro-update`), plus an optional **auto mode** to catch up. |
| Tooling | Custom. No Semaphore, AWX, Mender or Yocto for now. |

Consequences:

- `pi-manager-template` becomes this product.
- `pi-manager-fr` and `pi-manager-chile` are imported into their instance's database, then retired.

## 3. Architecture

```mermaid
flowchart TB
    OP(["Operator"])

    subgraph inst["Fleet instance: one docker compose per country, or local"]
        FRONT["Frontend"]
        FAPI["Fleet API<br/>(FastAPI)"]
        DB[("Postgres<br/>devices, params,<br/>encrypted secrets,<br/>deployments, jobs, audit")]
        WK["Worker<br/>jobs, retries, windows<br/>+ embedded Ansible"]
        FRONT --> FAPI
        FAPI <--> DB
        WK <--> DB
    end

    subgraph alert["Country alert API (already exists)"]
        AAPI["alert API<br/>cameras, poses, heartbeats"]
    end

    subgraph pis["Stations (Raspberry Pi, via VPN)"]
        UPD["pyro-update<br/>(local script)"]
        ENG["pyro-engine"]
        UPD --> ENG
    end

    subgraph vms["Server VMs"]
        SRV["alert API, platform,<br/>temporal API, traefik"]
    end

    OP --> FRONT
    FAPI -- "reads cameras, poses,<br/>running versions" --> AAPI
    WK -- "push over VPN<br/>(SSH host key checked)" --> UPD
    WK -- "night window" --> SRV
    ENG -- "heartbeat + version" --> AAPI
```

Two key points:

- **Decisions go down by push** (worker → Ansible → Pi).
- **What actually runs comes back up through the engine heartbeat** to the alert API. A deployment that "succeeded" is never used as proof of the running version.

### What lives where

```mermaid
flowchart LR
    subgraph AAPI["alert API (owner)"]
        A1["cameras, poses"]
        A2["engine heartbeat:<br/>last seen, running version"]
    end
    subgraph FAPI["Fleet API (owner)"]
        F1["devices: VPN IP, SSH host key,<br/>station assignment"]
        F2["engine params<br/>(non-camera settings)"]
        F3["secrets (encrypted)"]
        F4["desired version + mode<br/>(pinned / auto)"]
        F5["deployments, jobs, audit"]
    end
    FAPI -- "reads, never copies<br/>as editable data" --> AAPI
```

### Data model (first sketch)

```mermaid
erDiagram
    DEVICE ||--o{ JOB : "targeted by"
    DEVICE ||--o{ SECRET : has
    DEPLOYMENT ||--o{ JOB : "split into"
    DEVICE {
        int id
        string name
        string kind "engine | vm"
        string vpn_ip
        string ssh_host_key
        int alert_api_station_id
        json params
        string mode "pinned | auto"
        string desired_version
    }
    SECRET {
        int device_id
        string key
        bytes value_encrypted
    }
    DEPLOYMENT {
        int id
        string target "device | group | all"
        string version
        string strategy "single | canary_batches"
        time window_start
        time window_end
        string status
    }
    JOB {
        int id
        int deployment_id
        int device_id
        string status
        int attempts
        datetime next_try_at
        datetime expires_at
        text log
    }
    AUDIT {
        int id
        string user
        string action
        json details
        datetime at
    }
```

## 4. Updating an engine

### 4.1 Push, then local execution

The worker does not stay connected during the update. It drops `pyro-update` and the target version on the Pi, then starts it detached (`systemd-run`). If 4G drops in the middle, the Pi still finishes or rolls back on its own.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant F as Fleet API
    participant W as Worker
    participant Pi as Pi (pyro-update)
    participant A as alert API

    Op->>F: deploy v1.4.0 to device 42
    F->>F: create deployment + job (pending)
    W->>F: pick job inside its window
    W->>Pi: Ansible: check SSH host key, write target version
    W->>Pi: systemd-run pyro-update v1.4.0 (detached)
    W->>F: job = launched
    Note over Pi: pull, swap, health check<br/>rollback if unhealthy
    Pi->>A: engine heartbeat (version = 1.4.0 or 1.3.2)
    F->>A: read running version
    F->>F: job = success / rolled_back
```

### 4.2 What `pyro-update` does on the Pi

Everything that is needed to roll back (image, compose file, config, scripts) is kept locally before the working engine is touched.

```mermaid
flowchart TD
    S([start: target version]) --> P["docker pull target image<br/>(engine still running)"]
    P -- fails --> X1(["abort, engine untouched"])
    P -- ok --> SNAP["snapshot current release:<br/>image tag, compose, config, scripts"]
    SNAP --> SW["swap: start engine on target version"]
    SW --> HC{"healthy for N min?<br/>container up, cameras grabbed,<br/>frames processed"}
    HC -- yes --> OK(["success: keep new release,<br/>prune old images later"])
    HC -- no --> RB["rollback: restore snapshot"]
    RB --> BL["blacklist target tag locally"]
    BL --> KO(["rolled back"])
```

The health check must not depend on the alert API alone. If the country API is down, that is not a reason to roll back an engine.

### 4.3 Jobs: retries, windows, deadlines

Offline Pis are a normal state. A job waits for its device instead of failing.

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> waiting_window: outside window
    waiting_window --> pending: window opens
    pending --> running: device reachable
    pending --> retry: unreachable
    retry --> pending: backoff elapsed
    retry --> expired: past expires_at
    running --> success: healthy
    running --> rolled_back: unhealthy
    running --> failed: invalid config or credentials (no retry)
    pending --> cancelled: operator
    success --> [*]
    rolled_back --> [*]
    failed --> [*]
    expired --> [*]
    cancelled --> [*]
```

Rules:

- **One job at a time per device.**
- **A late job never starts outside its window.** A job planned for midnight that is still pending at 6:00 waits for the next window, or expires.
- **Errors that cannot be fixed by waiting** (bad config, bad credentials) are not retried.

### 4.4 "Update all" means waves

```mermaid
flowchart LR
    C["Canary<br/>1-2 devices"] --> G1{"all healthy?"}
    G1 -- no --> STOP(["pause campaign"])
    G1 -- yes --> B1["Batch<br/>~10%"] --> G2{"failures under<br/>threshold?"}
    G2 -- no --> STOP
    G2 -- yes --> B2["Rest of the fleet<br/>(bounded concurrency)"]
```

The operator can pause or cancel a campaign at any time.

## 5. Auto mode

Each device has a mode, stored in the Fleet API and written to the Pi by Ansible:

| Mode | Behaviour |
|---|---|
| `pinned: vX.Y.Z` | The nightly timer does nothing. Only a push changes the version. |
| `auto` | Every night, the Pi updates itself to the latest stable release, with the safeguards below. |

Auto mode is a systemd timer that runs `pyro-update --auto`. It lets a Pi that was offline for a long time catch up, even if no Fleet instance is running (for example a local instance on a laptop that is switched off).

```mermaid
flowchart TD
    T(["nightly timer<br/>+ random delay"]) --> M{"mode = auto?"}
    M -- no --> E1(["do nothing"])
    M -- yes --> R["resolve latest GitHub release of pyro-engine<br/>(no drafts, no pre-releases)"]
    R --> AGE{"published more than<br/>N days ago?"}
    AGE -- no --> E2(["wait: soak period"])
    AGE -- yes --> NEW{"newer than running<br/>and not blacklisted?"}
    NEW -- no --> E3(["do nothing"])
    NEW -- yes --> U["pyro-update vX.Y.Z<br/>(same flow as section 4.2)"]
```

Safeguards:

- **Never `:latest`.** It is overwritten on every merge to `main`. Only a published release counts, and the script logs the exact tag and digest.
- **Soak period** (for example 3 days). Pinned devices and pre-releases act as canaries before a release reaches auto devices.
- **Local blacklist.** A tag that failed its health check is never retried by the timer.
- **Random delay**, so that every Pi does not pull at the same minute over 4G.

Interaction with push:

- A push to an `auto` device switches it to `pinned`.
- **Summer freeze:** switch a group to `pinned` in one click. The Fleet API pushes the new mode without changing the version.

## 6. Updating the server VMs

Server updates (alert API, platform) run as scheduled jobs in a night window, from the country's server instance (not from a laptop that may be off at midnight).

```mermaid
sequenceDiagram
    actor Op as Operator
    participant F as Fleet API
    participant W as Worker
    participant VM as VM (alert API)

    Op->>F: update alert API to 1.0.18, tonight 00:00-04:00
    F->>F: create job (window, latest start 03:00)
    W->>F: 00:00 pick job
    W->>VM: Ansible: pull new image first
    W->>VM: restart the app container only (Postgres keeps running)
    VM->>VM: compatible migration (alembic upgrade head)
    W->>VM: health check through traefik
    alt healthy
        W->>F: success
    else unhealthy
        W->>VM: restart previous image
        W->>F: failed + notify operator
    end
```

This needs a change in the current roles. `alert_api` and `platform_react` start with `state: absent` and `remove_images: all`, which also stops Postgres. Restarting an old image does not undo a schema migration either, so migrations must stay backward compatible.

## 7. Prerequisites and known limits

- **Device identity.** Ansible runs with `host_key_checking = False`. The Fleet API stores each device's SSH host key and generates `known_hosts` for every job, so a wrong IP can never update the wrong station.
- **Running version.** Check whether the engine heartbeat already sends its version to the alert API. If not, it is a small change in the engine and the alert API.
- **Server roles.** Rewrite `alert_api` and `platform_react` so that an update never stops Postgres (section 6).
- **Local instance.** Scheduled jobs only run while the machine is on. Production night windows must run on a server instance.
- **No image tag from a branch name or `:latest`** in any deployment.
- **Detection never depends on the Fleet API.** If it is down, engines keep running.

## 8. Plan

```mermaid
flowchart LR
    S1["1. Read-only inventory<br/>import fr / chile repos,<br/>flag conflicts,<br/>show running versions"]
    S2["2. pyro-update<br/>+ deploy one device"]
    S3["3. Campaigns<br/>canary, batches,<br/>pause, cancel"]
    S4["4. Auto mode<br/>timer, soak, blacklist"]
    S5["5. VM night jobs<br/>(after fixing<br/>server roles)"]
    S6["6. Retire<br/>pi-manager-fr / chile"]
    S1 --> S2 --> S3 --> S4
    S1 --> S5
    S3 --> S6
    S5 --> S6
```

The cleanup issues (#57, #58, #59, #61, #62, #18) are re-evaluated against this plan: some become unnecessary once the country repos are retired, others (secrets in logs, `.env` modes) are still needed first.

## 9. Options considered

| Option | Why not (for now) |
|---|---|
| Keep Ansible + country repos, only clean up | Does not fix the duplicated sources of truth or the missing version view. |
| Pull agent on every Pi | Pis must reach the Fleet API at all times, which breaks local instances. We keep the door open: auto mode already uses the same script on a timer. |
| Semaphore / AWX | Runs Ansible, but has no model of stations, versions or rollouts. We would build that part anyway. |
| Mender / balena / Yocto | OS-level change, out of scope for now. |
| Watchtower | Updates on every new image, with no window, no waves and no rollback. Upstream is archived. |
