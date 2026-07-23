# Deployment Guide

> For a project overview and architecture, see [README.md](README.md).

This guide deploys the honeypot to a **Hetzner Cloud** VPS. Any Linux VPS works;
only the provisioning and firewall steps below are Hetzner-specific — everything
from "Upload All Files" onward is provider-agnostic.

---

## Provision the Server (Hetzner Cloud)

### 1. Create an account and project
- Sign up at [console.hetzner.cloud](https://console.hetzner.cloud) and create a
  new **Project**.
- New accounts occasionally get an identity-verification step before the first
  server can be created — this is normal fraud prevention, not a problem with
  your setup.

### 2. Add your SSH key
- **Security → SSH Keys → Add SSH Key**, and paste your public key
  (`~/.ssh/id_ed25519.pub` or `id_rsa.pub`). On Windows, generate one first with
  `ssh-keygen -t ed25519` in PowerShell if you don't have it.

### 3. Create the server
**Add Server**, then choose:
- **Location**: nearest region (Ashburn/Hillsboro for the US; Nuremberg,
  Falkenstein, Helsinki, or Singapore otherwise).
- **Image**: open the **Apps** tab and pick **Docker CE** so Docker comes
  pre-installed. (If you use a plain Ubuntu image instead, you'll install Docker
  in the next section — `setup.sh` will prompt you if it's missing.)
- **Type**: **CAX11** (ARM, the cheapest option, ~a few €/month) is plenty — the
  honeypot is tiny and the `python:3.11-slim` base image is multi-arch, so it
  builds natively on ARM. Prefer x86? Use **CX22** instead.
- **SSH key**: select the key you added.
- **Firewall**: attach the firewall you create below (or attach it afterward).
- **Create & Buy Now**, then note the server's **public IPv4 address**.

### 4. Configure the Cloud Firewall
Hetzner's Cloud Firewall sits in front of the VM and is stateful (return traffic
is allowed automatically). **Firewalls → Create Firewall** with these **inbound**
rules:

| Protocol | Port  | Source          | Purpose                         |
|----------|-------|-----------------|---------------------------------|
| TCP      | 25565 | `0.0.0.0/0`, `::/0` | The honeypot — open to the world |
| TCP      | 22    | `YOUR_IP/32`    | SSH — restrict to your own **public** IP |

Leave **outbound** at the default (allow all) — the build needs to pull the base
image. Apply the firewall to your server. Restricting SSH to your own IP means
the honeypot port is the only surface the internet can reach.

> **Find your public IP** with `Invoke-RestMethod ifconfig.me/ip` (PowerShell) or
> `curl ifconfig.me`. It must be the address the internet sees — *not* a private
> `10.x`, `192.168.x`, or `172.16–31.x` address from `ipconfig`/`ifconfig`, which
> won't match and will lock you out.

> Because the Cloud Firewall already gates traffic, you generally don't need
> `ufw` inside the VM. If you enable it anyway, remember to allow 25565 and 22
> there too.

> **Recommended: private SSH via Tailscale.** Rather than exposing port 22 to the
> internet and babysitting an IP allowlist, you can move SSH entirely inside a
> private [Tailscale](https://tailscale.com) network and delete the public port-22
> rule afterward — leaving 25565 as the *only* public surface. Keep the port-22
> rule for the initial bootstrap, then see [Private SSH via Tailscale](#private-ssh-via-tailscale-recommended) below.

---

## Step-by-Step Commands

### SSH into the VPS
Hetzner's Ubuntu/Docker images log you in as **root** by default:
```bash
# From your personal computer:
ssh root@YOUR_VPS_IP
```

### Create a non-root user
`setup.sh` refuses to run as root, and the container is designed to run as an
unprivileged user. Create one, give it Docker access, and copy your SSH key so
you can log in as it:
```bash
# On the VPS, as root:
adduser --disabled-password --gecos "" honeypot
usermod -aG docker honeypot
rsync --archive --chown=honeypot:honeypot ~/.ssh /home/honeypot/
```
Then log out and back in as the honeypot user:
```bash
ssh honeypot@YOUR_VPS_IP
```

### Install Docker (only if you did NOT use the Docker CE app image)
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # then log out and back in
```

### Upload All Files
```bash
# From your personal computer (in the directory with the files):
scp minecraft_honeypot.py Dockerfile docker-compose.yml README.md setup.sh honeypot@YOUR_VPS_IP:~/
scp analyze_logs.py attack_simulator.py honeypot@YOUR_VPS_IP:~/
```

### Run Setup Script
```bash
# On the VPS:
chmod +x setup.sh
./setup.sh
```

The script does everything:
- Creates logs directory
- Records your uid/gid in `.env` so the container runs as you
- Builds Docker image
- Starts the honeypot
- Verifies it's running

> **Docker Compose is the v2 plugin** — invoked as `docker compose` (with a
> space), not the deprecated standalone `docker-compose` binary. The Hetzner
> "Docker CE" app image already includes it. If `docker compose version` fails,
> install it with `sudo apt update && sudo apt install -y docker-compose-plugin`.

---

## Private SSH via Tailscale (recommended)

Exposing SSH to the public internet — even restricted to your IP — means it
breaks whenever your ISP rotates your address, and it's one more public surface
on a box that deliberately attracts attackers. [Tailscale](https://tailscale.com)
moves SSH entirely onto a private network so the honeypot's *only* public surface
is port 25565.

Do this **after** the honeypot is running (you still needed the temporary port-22
rule to bootstrap):

1. **Install Tailscale on the VPS** (run as **root** — it's a system-wide daemon;
   the `honeypot` user has no sudo):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   tailscale up                       # open the printed URL, sign in, approve
   tailscale ip -4                    # note this 100.x.x.x address
   ```

2. **Lock the honeypot down with an ACL** so it can be *reached* but can't *initiate*
   connections to your other devices (limits lateral movement if it's ever
   compromised). In the Tailscale admin console:
   - **Machines → the honeypot → ⋯ → Edit ACL tags →** add `tag:honeypot`
     (or run `sudo tailscale up --advertise-tags=tag:honeypot` on the VPS).
   - **Access Controls →** ensure the only rule is **Source = your user →
     Destination = all → all ports.** Because the honeypot is now *tagged* (not
     owned by your user), it isn't a permitted source, so it can't reach back
     into your tailnet. (Note: `tailscale ping` bypasses ACLs and will still
     succeed — use the console's rule tester to verify a real Deny.)

3. **Verify Tailscale SSH works**, then remove the public rule:
   ```bash
   # From your PC — should log in over the 100.x address:
   ssh honeypot@SERVER_TS_IP
   ```
   Once that works, delete the **TCP 22** rule from the Hetzner Cloud Firewall.
   SSH is now private to your tailnet; only 25565 remains public.

> ⚠️ Don't delete the port-22 rule until Tailscale SSH is confirmed working, or
> you'll lock yourself out. If that happens, Hetzner's web **Console** button on
> the server page always gets you back in.

From here on, connect with `ssh honeypot@SERVER_TS_IP` (your Tailscale `100.x`
address, or its MagicDNS name).

---

## Alternative: Manual Setup

If you prefer to do it manually:

```bash
# Create logs directory
mkdir -p logs

# Record your uid/gid so the container can write to logs/
# (skip only if your VPS user is uid 1000, the compose default)
printf 'HONEYPOT_UID=%s\nHONEYPOT_GID=%s\n' "$(id -u)" "$(id -g)" > .env

# Build Docker image
docker compose build

# Start honeypot
docker compose up -d

# Verify it's running
docker ps

# View logs
docker logs -f minecraft-honeypot
```

---

## Hardened Runtime (what to expect)

The container is locked down on purpose — it deliberately attracts hostile traffic, so the blast radius of any bug is kept minimal:

- Runs as a **non-root** user — specifically **your host user's uid/gid**, so the bind-mounted `logs/` is writable by both the container and you
- **Read-only** root filesystem — the only writable paths are the mounted `logs/` volume and a small non-persistent `/tmp` tmpfs
- **All Linux capabilities dropped** (`cap_drop: ALL`) with `no-new-privileges`
- **Resource caps**: `mem_limit: 256m`, `pids_limit: 256`, `cpus: 0.5`
- Handles connections **concurrently** (one thread each, capped at 200) so a slow/silent client can't stall the honeypot

**Container user / `logs/` permissions.** `setup.sh` writes a `.env` file with your `HONEYPOT_UID`/`HONEYPOT_GID`, and docker compose reads it automatically for every command (`up`, `restart`, etc.). If you deploy manually without `setup.sh`, either create that `.env` yourself or rely on the compose default of `1000` (the typical first VPS user):

```bash
printf 'HONEYPOT_UID=%s\nHONEYPOT_GID=%s\n' "$(id -u)" "$(id -g)" > .env
```

Other implications:
- Don't expect to write files anywhere inside the container except `/logs`. If you customize it to write elsewhere, add a `tmpfs` or volume — the root FS is immutable.
- `docker stats` will show memory capped at ~256 MiB. If the container is OOM-killed under heavy load, raise `mem_limit` in `docker-compose.yml`.

---

## Quick Commands Reference

### Viewing Logs
```bash
# Real-time logs
docker logs -f minecraft-honeypot

# Last 50 lines
docker logs minecraft-honeypot --tail 50

# Analyze statistics
python3 analyze_logs.py

# View recent connections (optionally from a specific log file)
python3 analyze_logs.py recent 10
python3 analyze_logs.py recent 10 logs/connections.jsonl
```

### Managing Honeypot
```bash
# Stop
docker compose down

# Start
docker compose up -d

# Restart
docker compose restart

# Rebuild after changes
docker compose down && docker compose build && docker compose up -d
```

### Testing
```bash
# From your personal computer:
python3 attack_simulator.py YOUR_VPS_IP

# Or test with Minecraft client:
# Add server: YOUR_VPS_IP:25565
```

### Monitoring
```bash
# Check if running
docker ps | grep honeypot

# Resource usage (memory is capped at ~256 MiB by mem_limit)
docker stats minecraft-honeypot

# Disk usage
du -sh logs/

# Connection count
wc -l logs/connections.jsonl
```

### Downloading Results
```bash
# From your personal computer:
scp -r honeypot@YOUR_VPS_IP:~/logs ./honeypot-results

# Then analyze locally:
python3 analyze_logs.py honeypot-results/connections.jsonl
```

---

## Most Used Commands

```bash
# Start everything
./setup.sh

# Watch attacks in real-time
docker logs -f minecraft-honeypot

# See statistics
python3 analyze_logs.py

# Stop when done
docker compose down
```

---

## Troubleshooting

### Honeypot won't start?
```bash
# Check what went wrong
docker logs minecraft-honeypot

# Check if port is in use
sudo netstat -tulpn | grep 25565

# Rebuild from scratch
docker compose down
docker system prune -a -f
docker compose build --no-cache
docker compose up -d
```

Note: the container runs with a **read-only root filesystem** as your host
user. Two related symptoms:
- **"Read-only file system"** — the process tried to write outside the allowed
  paths (`/logs` and `/tmp`). Make sure `logs/` exists on the host: `mkdir -p logs`.
- **"Permission denied" writing to `/logs`** — the container's uid doesn't own
  `logs/`. Regenerate the `.env` so the container runs as you, then restart:
  ```bash
  printf 'HONEYPOT_UID=%s\nHONEYPOT_GID=%s\n' "$(id -u)" "$(id -g)" > .env
  docker compose down && docker compose up -d
  ```

### Container gets OOM-killed / keeps restarting under load?
The container is capped at `mem_limit: 256m`. Under an unusually heavy flood it
may be killed and restarted. Raise the limit in `docker-compose.yml` and
rebuild:
```bash
docker compose down && docker compose up -d
```

### No attacks yet?
- Wait 24-48 hours for scanners to find you
- Test manually: `python3 attack_simulator.py YOUR_VPS_IP`
- Check the **Hetzner Cloud Firewall**: an inbound rule must allow TCP 25565 from
  `0.0.0.0/0` (and `::/0`), and the firewall must be attached to the server
- If you also run `ufw` inside the VM, confirm 25565 is open there too:
  `sudo ufw status`

### Can't SSH in?
```bash
# From personal computer, check the connection
ssh -v honeypot@YOUR_VPS_IP
```
- Confirm the Cloud Firewall allows TCP 22 from your current IP (if your ISP
  changed your IP, update the `YOUR_IP/32` rule in the Hetzner Console)
- Check the server is running in the Hetzner Cloud Console

---

## 💰 Cost Management

Hetzner Cloud bills **hourly** up to a monthly cap, so a stopped-and-deleted
server costs only for the hours it existed. A CAX11 runs a few €/month if left on
continuously.

### Check uptime
```bash
docker ps  # See "Up X hours/days"
```

### Stop to save money
```bash
# Keep logs but stop the container (server still billed while it exists)
docker compose down

# Restart later
docker compose up -d
```

> To stop billing entirely you must **delete the server** in the Hetzner Console
> (powering it off still incurs charges). Back up your logs first — see below.

### Backup before deleting the server
```bash
# Download logs to your personal computer
scp -r honeypot@YOUR_VPS_IP:~/logs ./honeypot-backup-$(date +%Y%m%d)
```

---

## Expected Results

After **24 hours**:
- 50-200 connections
- 20-80 unique IPs
- Mix of status checks and login attempts

After **1 week**:
- 500-2000 connections
- 200-500 unique IPs
- Clear attack patterns emerging

---

## Your First Day Checklist

- [ ] Create Hetzner Cloud account and a project
- [ ] Add your SSH key (Security → SSH Keys)
- [ ] Create a CAX11 server from the **Docker CE** app image
- [ ] Create a Cloud Firewall: inbound TCP 25565 from anywhere, TCP 22 from your IP
- [ ] Attach the firewall to the server
- [ ] SSH in as root, create the `honeypot` user, copy your SSH key
- [ ] Upload files to VPS
- [ ] Run `./setup.sh`
- [ ] Verify honeypot is running: `docker ps`
- [ ] Test from personal computer: `python3 attack_simulator.py YOUR_VPS_IP`
- [ ] Check logs appear: `python3 analyze_logs.py`
- [ ] (Recommended) Set up [Tailscale SSH](#private-ssh-via-tailscale-recommended), tag the honeypot, then delete the public TCP 22 firewall rule
- [ ] Wait 24 hours
- [ ] Check statistics: `python3 analyze_logs.py`
- [ ] Learn from the attacks!
