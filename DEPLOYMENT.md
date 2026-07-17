# Deployment Guide

> For a project overview and architecture, see [README.md](README.md).

## Step-by-Step Commands to Run on VPS

### SSH into  VPS
```bash
# From  personal computer:
ssh honeypot@YOUR_VPS_IP
```

### Upload All Files
```bash
# From  personal computer (in directory with files):
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
- Builds Docker image
- Starts the honeypot
- Verifies it's running

---

## Alternative: Manual Setup

If prefer to do it manually:

```bash
# Create logs directory
mkdir -p logs

# Build Docker image
docker-compose build

# Start honeypot
docker-compose up -d

# Verify it's running
docker ps

# View logs
docker logs -f minecraft-honeypot
```

---

## Hardened Runtime (what to expect)

The container is locked down on purpose — it deliberately attracts hostile traffic, so the blast radius of any bug is kept minimal:

- Runs as a **non-root** `honeypot` user
- **Read-only** root filesystem — the only writable paths are the mounted `logs/` volume and a small non-persistent `/tmp` tmpfs
- **All Linux capabilities dropped** (`cap_drop: ALL`) with `no-new-privileges`
- **Resource caps**: `mem_limit: 256m`, `pids_limit: 256`, `cpus: 0.5`
- Handles connections **concurrently** (one thread each, capped at 200) so a slow/silent client can't stall the honeypot

Implications for deployment:
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
docker-compose down

# Start
docker-compose up -d

# Restart
docker-compose restart

# Rebuild after changes
docker-compose down && docker-compose build && docker-compose up -d
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
docker-compose down
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
docker-compose down
docker system prune -a -f
docker-compose build --no-cache
docker-compose up -d
```

Note: the container runs with a **read-only root filesystem**. If you see
"Read-only file system" errors, the process is trying to write outside the
allowed paths (`/logs` and `/tmp`). Make sure the `logs/` volume exists and is
writable on the host: `mkdir -p logs`.

### Container gets OOM-killed / keeps restarting under load?
The container is capped at `mem_limit: 256m`. Under an unusually heavy flood it
may be killed and restarted. Raise the limit in `docker-compose.yml` and
rebuild:
```bash
docker-compose down && docker-compose up -d
```

### No attacks yet?
- Wait 24-48 hours for scanners to find you
- Test manually: `python3 attack_simulator.py YOUR_VPS_IP`
- Check firewall: `sudo ufw status` (port 25565 should be open)

### Can't SSH in?
```bash
# From personal computer, check connection
ssh -v honeypot@YOUR_VPS_IP

# Check if VPS is running on DigitalOcean web interface
```

---

## 💰 Cost Management

### Check uptime
```bash
docker ps  # See "Up X hours/days"
```

### Stop to save money
```bash
# Keep logs but stop container
docker-compose down

# Restart later
docker-compose up -d
```

### Backup before destroying VPS
```bash
# Download logs to personal computer
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

- [ ] Create DigitalOcean account
- [ ] Add SSH key
- [ ] Create $6/month Docker droplet
- [ ] Upload files to VPS
- [ ] Run `./setup.sh`
- [ ] Verify honeypot is running: `docker ps`
- [ ] Test from personal computer: `python3 attack_simulator.py YOUR_VPS_IP`
- [ ] Check logs appear: `python3 analyze_logs.py`
- [ ] Wait 24 hours
- [ ] Check statistics: `python3 analyze_logs.py`
- [ ] Learn from the attacks!
