# Multi-Protocol Honeypot

A Dockerized honeypot server that emulates a Minecraft game server to capture and analyze real-world network reconnaissance and attack traffic. Deployed on a VPS and exposed on the standard Minecraft port (25565), it passively collects connection attempts from automated scanners, login bots, and exploit probes without running any actual game logic.

## Architecture

- **`minecraft_honeypot.py`** — Core honeypot server. Speaks enough of the Minecraft protocol to satisfy a connecting client through the handshake phase, then logs and drops the connection. Never executes any game state.
- **`analyze_logs.py`** — Log analysis tool. Parses the structured JSONL connection log and reports connection volume, top source IPs, protocol versions, connection types, and attack timelines.
- **`attack_simulator.py`** — Local test harness. Fires five distinct probe types against a target IP so you can verify honeypot behavior without waiting for organic traffic.
- **`Dockerfile` / `docker-compose.yml`** — Container setup. Isolates the honeypot process from the host; the only exposure is port 25565.

## Deployment

### 1. Transfer files to your VPS

```bash
scp minecraft_honeypot.py Dockerfile docker-compose.yml honeypot@YOUR_VPS_IP:~/
scp analyze_logs.py attack_simulator.py honeypot@YOUR_VPS_IP:~/
```

### 2. Build and start

```bash
docker-compose build
docker-compose up -d
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
| `logs/connections.jsonl` | JSONL | One JSON object per connection — source IP, timestamp, protocol version, connection type, errors |

### Running the analyzer

```bash
python3 analyze_logs.py           # summary report
python3 analyze_logs.py recent 20 # last 20 connections in detail
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
docker-compose down

# Restart
docker-compose restart

# Rebuild after code changes
docker-compose down && docker-compose build && docker-compose up -d

# Clear logs (stop first)
docker-compose down && rm -rf logs/* && docker-compose up -d

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
docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

## Security Considerations

- The honeypot runs fully inside Docker with no shared volumes beyond `logs/`
- Port 25565 is the only exposed surface
- Do not run additional services on the same VPS
- Monitor bandwidth; high-volume DoS probes can generate significant egress

## Next Steps

- Capture and store full packet payloads for deeper protocol analysis
- Add alerting (email/webhook) for high-frequency source IPs
- Integrate with an ELK stack or Grafana for time-series visualization
- Deploy instances across multiple regions to compare geographic attack patterns
- Cross-reference source IPs against known threat intelligence feeds
