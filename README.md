# Multi-Protocol Honeypot

A Dockerized honeypot server that emulates a Minecraft game server to capture and analyze real-world network reconnaissance and attack traffic. Deployed on a VPS and exposed on the standard Minecraft port (25565), it passively collects connection attempts from automated scanners, login bots, and exploit probes without running any actual game logic.

> **Scope note:** The repository is named *Multi-Protocol* to reflect the intended direction. Today it emulates a **single protocol — Minecraft**. Additional protocol emulators (SSH, Telnet, HTTP, etc.) are on the roadmap, not yet implemented.

## Architecture

- **`minecraft_honeypot.py`** — Core honeypot server. Speaks enough of the Minecraft protocol to satisfy a connecting client through the handshake phase, then logs and drops the connection. Never executes any game state. Each connection is handled in its own thread (bounded by a concurrency cap), so a slow or silent client can't stall the server. Packets are framed by their declared VarInt length — correct even when the client coalesces the handshake and status request into one segment or splits a packet across several — and it completes the status + ping/pong exchange so it looks like a real server.
- **`analyze_logs.py`** — Log analysis tool. Parses the structured JSONL connection log and reports connection volume, top source IPs, protocol versions, connection types, and attack timelines.
- **`attack_simulator.py`** — Local test harness. Fires five distinct probe types against a target IP so you can verify honeypot behavior without waiting for organic traffic.
- **`Dockerfile` / `docker-compose.yml`** — Container setup. Isolates the honeypot process from the host; the only exposure is port 25565.

## Deployment

> For a guided, script-driven setup (including a Hetzner Cloud walkthrough and `setup.sh`), see [DEPLOYMENT.md](DEPLOYMENT.md). The steps below are the manual equivalent.

### 1. Transfer files to your VPS

```bash
scp minecraft_honeypot.py Dockerfile docker-compose.yml honeypot@YOUR_VPS_IP:~/
scp analyze_logs.py attack_simulator.py honeypot@YOUR_VPS_IP:~/
```

### 2. Build and start

```bash
# Record your uid/gid so the container can write to logs/ (setup.sh does this
# for you). Skip only if your VPS user is uid 1000, the compose default.
printf 'HONEYPOT_UID=%s\nHONEYPOT_GID=%s\n' "$(id -u)" "$(id -g)" > .env

docker compose build
docker compose up -d
docker ps   # confirm the container is running
```

Expected output:
```
CONTAINER ID   IMAGE               STATUS         PORTS
abc123def456   minecraft-honeypot  Up 2 seconds   0.0.0.0:25565->25565/tcp
```

### 3. Monitor live traffic

```bash
docker logs -f minecraft-honeypot
```

## Log Analysis

Logs are written to `logs/` inside the container, mounted to the host:

| File | Format | Contents |
|---|---|---|
| `logs/honeypot.log` | Plain text | Human-readable event stream |
| `logs/connections.jsonl` | JSONL | One JSON object per connection — source IP/port, timestamp, per-packet summaries, handshake details (protocol version, requested address, next state), any login username, and errors |

### Running the analyzer

```bash
python3 analyze_logs.py                     # summary report (default log path)
python3 analyze_logs.py path/to/log.jsonl   # summary of a specific log file
python3 analyze_logs.py recent 20           # last 20 connections in detail
python3 analyze_logs.py recent 20 log.jsonl # last 20 from a specific log file
```

Sample output after 24 hours of exposure:

```
MINECRAFT HONEYPOT - LOG ANALYSIS
======================================================================

Total Connections: 127

Top Source IPs:
  185.220.101.45    -  23 connections
  192.42.116.186    -  15 connections
  167.99.84.203     -  12 connections

Unique IPs: 89

Connection Types:
  Status   -  98 connections
  Login    -  29 connections
```

### Useful queries against the JSONL log

```bash
# IPs that only issued status pings (scanner bots)
grep "next_state_name.*status" logs/connections.jsonl

# Login attempts
grep "next_state_name.*login" logs/connections.jsonl

# Malformed or error-generating packets
grep "error" logs/connections.jsonl

# Unique source IPs
jq -r '.source_ip' logs/connections.jsonl | sort -u

# Daily connection volume
jq -r '.timestamp' logs/connections.jsonl | cut -d'T' -f1 | sort | uniq -c
```

## Testing

Run the attack simulator from a separate machine (not the VPS itself) to verify all probe types are captured:

```bash
python3 attack_simulator.py YOUR_VPS_IP
```

This fires five probe types:
1. **Server List Ping** — standard status handshake
2. **Login Attempt** — full login sequence initiation
3. **Old Protocol** — outdated client version
4. **Malformed Packet** — garbage payload
5. **Rapid Connections** — burst of quick successive connects

You can also connect with the real Minecraft client by adding `YOUR_VPS_IP:25565` as a server — the honeypot will appear in the server list and log the attempt.

## Management

```bash
# Stop
docker compose down

# Restart
docker compose restart

# Rebuild after code changes
docker compose down && docker compose build && docker compose up -d

# Clear logs (stop first)
docker compose down && rm -rf logs/* && docker compose up -d

# Resource usage
docker stats minecraft-honeypot

# Download logs to local machine
scp -r honeypot@YOUR_VPS_IP:~/logs ./honeypot-logs
```

## Troubleshooting

**Container won't start**
```bash
sudo netstat -tulpn | grep 25565   # check if port is already bound
docker logs minecraft-honeypot     # inspect startup errors
```

**No traffic after deployment**
- Internet scanners typically find new IPs within 24–48 hours
- Verify the port is reachable: `python3 attack_simulator.py YOUR_VPS_IP`
- Check the firewall: `sudo ufw status`

**Container restart loop**
```bash
docker logs minecraft-honeypot --tail 100
docker compose down && docker compose build --no-cache && docker compose up -d
```

## Security Considerations

Because the honeypot deliberately attracts hostile traffic, it is hardened to keep the blast radius of any bug as small as possible:

- **Non-root process** — the container never runs as root. It runs as your unprivileged host user (uid/gid), which also keeps the bind-mounted `logs/` writable by both the container and you. `setup.sh` records your uid/gid in a `.env` file; without it the compose file defaults to `1000` (the typical first VPS user)
- **Immutable root filesystem** — `read_only: true`; `logs/` is the only writable path (plus a small non-persistent `tmpfs` at `/tmp`)
- **No Linux capabilities** — `cap_drop: ALL` with `no-new-privileges` to block setuid escalation
- **Resource caps** — `mem_limit`, `pids_limit`, and `cpus` bound the container so a flood can't exhaust the host
- **Input limits in code** — per-packet (32 KB) and per-connection (64 KB) byte caps, plus a bounded concurrency limit, guard against memory/thread exhaustion
- **No code execution** — attacker-supplied bytes are only framed and logged, never evaluated
- Port 25565 is the only exposed surface — do not run additional services on the same VPS
- Monitor bandwidth; high-volume DoS probes can generate significant egress

> The honeypot reads its log directory from `HONEYPOT_LOG_DIR` (defaults to `/logs`, the container mount). This lets you run it locally for development without touching the container config.

## Next Steps

- Add emulators for additional protocols (SSH, Telnet, HTTP) to make the "multi-protocol" name literal
- Capture and store full packet payloads for deeper protocol analysis
- Add alerting (email/webhook) for high-frequency source IPs
- Integrate with an ELK stack or Grafana for time-series visualization
- Deploy instances across multiple regions to compare geographic attack patterns
- Cross-reference source IPs against known threat intelligence feeds
