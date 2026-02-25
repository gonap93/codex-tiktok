# Postiz Self-Hosted on Hetzner — Full Configuration & Monitoring Guide

---

## Table of Contents

1. [Server Setup (Hetzner Cloud)](#1-server-setup-hetzner-cloud)
2. [System Preparation](#2-system-preparation)
3. [Docker & Docker Compose](#3-docker--docker-compose)
4. [Project Files & Environment Variables](#4-project-files--environment-variables)
5. [Nginx Reverse Proxy + SSL](#5-nginx-reverse-proxy--ssl)
6. [Firewall Rules](#6-firewall-rules)
7. [Starting the Stack](#7-starting-the-stack)
8. [Monitoring — Step by Step](#8-monitoring--step-by-step)
   - [8.1 Container Health & Logs](#81-container-health--logs)
   - [8.2 System Resources (htop / ctop)](#82-system-resources-htop--ctop)
   - [8.3 Uptime Kuma (Uptime Dashboard)](#83-uptime-kuma-uptime-dashboard)
   - [8.4 Hetzner Cloud Built-in Metrics](#84-hetzner-cloud-built-in-metrics)
   - [8.5 PostgreSQL Monitoring](#85-postgresql-monitoring)
   - [8.6 Redis Monitoring](#86-redis-monitoring)
   - [8.7 Temporal Monitoring (UI)](#87-temporal-monitoring-ui)
   - [8.8 Sentry / Spotlight (Error Tracking)](#88-sentry--spotlight-error-tracking)
   - [8.9 Log Rotation](#89-log-rotation)
9. [Backup Strategy](#9-backup-strategy)
10. [Useful Commands Cheatsheet](#10-useful-commands-cheatsheet)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Server Setup (Hetzner Cloud)

### Recommended Server Spec

| Resource | Minimum | Recommended |
|---|---|---|
| Type | CX22 (2 vCPU / 4 GB) | CX32 (4 vCPU / 8 GB) |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| Volume | 40 GB local | 80 GB local + optional volume |
| Location | Any | Pick closest to your users |

> **Note:** Temporal + OpenSearch are memory-hungry. The full stack with Temporal requires at least 6–8 GB RAM. Consider CX32 or higher.

### Steps in Hetzner Cloud Console

1. Go to [console.hetzner.cloud](https://console.hetzner.cloud)
2. Create a new **Project**
3. Click **Add Server**
4. Select: Ubuntu 24.04, your preferred region, CX32 (or higher)
5. Add your **SSH public key** (strongly recommended over password)
6. Enable **Hetzner Cloud Backups** (optional but recommended, +20% cost)
7. Add server to a **Private Network** if you plan to run multiple servers later
8. Note the **public IPv4** assigned to the server

---

## 2. System Preparation

SSH into your server and run everything below as root or with sudo.

```bash
ssh root@<YOUR_SERVER_IP>
```

### Update the system

```bash
apt update && apt upgrade -y
apt install -y curl wget git unzip htop ufw fail2ban nginx certbot python3-certbot-nginx
```

### Create a non-root deploy user (optional but good practice)

```bash
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy   # add after docker install
```

### Set timezone

```bash
timedatectl set-timezone Europe/Berlin   # or your timezone
```

---

## 3. Docker & Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add current user to docker group (if using non-root user)
usermod -aG docker $USER

# Verify
docker --version
docker compose version
```

---

## 4. Project Files & Environment Variables

### Clone or upload the postiz directory

```bash
mkdir -p /opt/postiz
cd /opt/postiz
```

Copy the contents of your `postiz/` folder to `/opt/postiz/` on the server:

```bash
# From your local machine:
scp -r ./postiz/* root@<YOUR_SERVER_IP>:/opt/postiz/
```

Your `/opt/postiz/` should look like:

```
/opt/postiz/
├── docker-compose.yml
├── dynamicconfig/
│   └── development-sql.yaml
├── .env                  # Postgres credentials (create this)
└── .postiz.env           # Postiz app config (create this)
```

---

### `.env` — Postgres Credentials

```bash
cat > /opt/postiz/.env << 'EOF'
POSTGRES_USER=postiz-user
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=postiz-db-local
EOF
```

> Replace `CHANGE_ME_STRONG_PASSWORD` with a strong random password.

---

### `.postiz.env` — Postiz Application Config

```bash
cat > /opt/postiz/.postiz.env << 'EOF'
# ── URLs (replace with your actual domain) ──────────────────────────────────
MAIN_URL=https://postiz.yourdomain.com
FRONTEND_URL=https://postiz.yourdomain.com
NEXT_PUBLIC_BACKEND_URL=https://postiz.yourdomain.com/api
BACKEND_INTERNAL_URL=http://localhost:3000

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postiz-user:CHANGE_ME_STRONG_PASSWORD@postiz-postgres:5432/postiz-db-local

# ── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL=redis://postiz-redis:6379

# ── Storage (local by default, or configure S3) ──────────────────────────────
STORAGE_PROVIDER=local
UPLOAD_DIRECTORY=/uploads
NEXT_PUBLIC_UPLOAD_STATIC_DIRECTORY=/uploads

# ── Auth / Secrets ────────────────────────────────────────────────────────────
# Generate with: openssl rand -base64 32
JWT_SECRET=CHANGE_ME_JWT_SECRET_32_CHARS_MIN
NEXTAUTH_SECRET=CHANGE_ME_NEXTAUTH_SECRET

# ── Temporal ─────────────────────────────────────────────────────────────────
TEMPORAL_INTERNAL_URL=temporal:7233
RUN_CRON=true

# ── Email (configure SMTP for notifications) ─────────────────────────────────
EMAIL_FROM_NAME=Postiz
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
# SENDGRID_API_KEY=your_key
# or SMTP:
# SMTP_HOST=smtp.example.com
# SMTP_PORT=587
# SMTP_USER=user
# SMTP_PASS=pass

# ── Misc ─────────────────────────────────────────────────────────────────────
NX_ADD_PLUGINS=false
NODE_ENV=production
EXTENSION_ID=icpokdlcikdmemjkeoojhocmhmehpaia
EOF
```

Generate secrets:

```bash
openssl rand -base64 32  # use output for JWT_SECRET
openssl rand -base64 32  # use output for NEXTAUTH_SECRET
```

---

## 5. Nginx Reverse Proxy + SSL

### Create Nginx config

```bash
cat > /etc/nginx/sites-available/postiz << 'EOF'
server {
    listen 80;
    server_name postiz.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name postiz.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/postiz.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/postiz.yourdomain.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass         http://127.0.0.1:4007;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
    }

    # Temporal UI (optional, restrict access)
    location /temporal/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        # Restrict to your IP only:
        # allow YOUR.IP.ADDRESS;
        # deny all;
    }
}
EOF

ln -s /etc/nginx/sites-available/postiz /etc/nginx/sites-enabled/
nginx -t
```

### Get SSL certificate

```bash
certbot --nginx -d postiz.yourdomain.com
```

Follow prompts. Certbot will auto-renew via systemd timer.

```bash
# Test auto-renewal
certbot renew --dry-run
```

---

## 6. Firewall Rules

```bash
# Allow SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 'Nginx Full'

# Temporal gRPC (only if needed externally, otherwise keep closed)
# ufw allow 7233/tcp

# Enable firewall
ufw enable
ufw status verbose
```

> **Important:** Ports 4007, 8080, 8969 should NOT be exposed externally — traffic goes through Nginx only.

---

## 7. Starting the Stack

```bash
cd /opt/postiz

# Pull all images first
docker compose pull

# Start everything in detached mode
docker compose up -d

# Check status
docker compose ps
```

Wait ~2 minutes for all services to become healthy (especially Temporal + OpenSearch).

```bash
# Confirm all containers are Up and healthy
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:

```
NAME                    STATUS                     PORTS
postiz                  Up (healthy)               0.0.0.0:4007->5000/tcp
postiz-postgres         Up (healthy)               5432/tcp
postiz-redis            Up (healthy)               6379/tcp
temporal                Up                         0.0.0.0:7233->7233/tcp
temporal-postgresql     Up                         5432/tcp
temporal-elasticsearch  Up                         9200/tcp
temporal-ui             Up                         0.0.0.0:8080->8080/tcp
temporal-admin-tools    Up
spotlight               Up                         0.0.0.0:8969->8969/tcp
```

---

## 8. Monitoring — Step by Step

### 8.1 Container Health & Logs

#### Check all container statuses

```bash
docker compose -f /opt/postiz/docker-compose.yml ps
```

#### Tail live logs for all services

```bash
docker compose -f /opt/postiz/docker-compose.yml logs -f
```

#### Tail logs for a specific service

```bash
# Postiz app
docker logs -f postiz --tail 100

# Postgres
docker logs -f postiz-postgres --tail 50

# Redis
docker logs -f postiz-redis --tail 50

# Temporal
docker logs -f temporal --tail 100
```

#### Check a container's health status in detail

```bash
docker inspect postiz | grep -A 10 '"Health"'
docker inspect postiz-postgres | grep -A 10 '"Health"'
docker inspect postiz-redis | grep -A 10 '"Health"'
```

---

### 8.2 System Resources (htop / ctop)

#### htop — Interactive process monitor

```bash
htop
```

Key things to watch:
- CPU per core (top bar)
- Memory usage (avoid going above 80%)
- Load average (should be < number of CPU cores)

#### ctop — Docker-specific container metrics

```bash
# Install ctop
wget https://github.com/bcicen/ctop/releases/latest/download/ctop-0.7.7-linux-amd64 -O /usr/local/bin/ctop
chmod +x /usr/local/bin/ctop

ctop
```

`ctop` shows per-container: CPU %, MEM usage, NET I/O, BLOCK I/O — press `q` to quit.

#### docker stats — Live resource stream

```bash
# All containers
docker stats

# Specific containers only
docker stats postiz postiz-postgres postiz-redis temporal
```

---

### 8.3 Uptime Kuma (Uptime Dashboard)

Uptime Kuma is a self-hosted uptime monitor with a clean UI. Run it as a separate container.

```bash
docker run -d \
  --name uptime-kuma \
  --restart always \
  -p 3001:3001 \
  -v uptime-kuma-data:/app/data \
  louislam/uptime-kuma:latest
```

Access at: `http://YOUR_SERVER_IP:3001` (add Nginx proxy + auth if exposing)

**Monitors to configure inside Uptime Kuma:**

| Monitor Name | Type | URL / Target | Interval |
|---|---|---|---|
| Postiz App | HTTP(s) | `https://postiz.yourdomain.com` | 60s |
| Postiz API | HTTP(s) | `https://postiz.yourdomain.com/api/status` | 60s |
| Postgres | TCP Port | `localhost:5432` | 60s |
| Redis | TCP Port | `localhost:6379` | 60s |
| Temporal | TCP Port | `localhost:7233` | 60s |

Set up **email/Telegram/Slack notifications** in Uptime Kuma Settings → Notifications.

---

### 8.4 Hetzner Cloud Built-in Metrics

In **Hetzner Cloud Console → Your Server → Graphs**:

- **CPU** — view last 24h / 7d / 30d
- **Disk I/O** — watch for sustained high read/write (signals DB issues)
- **Network** — unusual spikes may indicate abuse

**Enable Hetzner Monitoring alerts:**

1. Go to your server → **Monitoring** tab
2. Set CPU alert threshold: **> 80% for 5 minutes**
3. Set alerts to send to your email

---

### 8.5 PostgreSQL Monitoring

#### Connect to Postgres

```bash
docker exec -it postiz-postgres psql -U postiz-user -d postiz-db-local
```

#### Useful queries inside psql

```sql
-- Active connections
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

-- Database size
SELECT pg_size_pretty(pg_database_size('postiz-db-local'));

-- Table sizes
SELECT
  relname AS table,
  pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;

-- Long-running queries (> 30s)
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle' AND now() - query_start > interval '30 seconds';

-- Quit
\q
```

#### Check DB disk usage from shell

```bash
docker exec postiz-postgres du -sh /var/lib/postgresql/data
```

---

### 8.6 Redis Monitoring

#### Connect to Redis

```bash
docker exec -it postiz-redis redis-cli
```

#### Useful Redis commands

```bash
# Server info overview
INFO server

# Memory usage
INFO memory

# Connected clients
INFO clients

# Number of keys
DBSIZE

# Monitor live commands (verbose, use briefly)
MONITOR

# Slowlog — last 10 slow queries
SLOWLOG GET 10

# Exit
quit
```

#### One-liner health check from shell

```bash
docker exec postiz-redis redis-cli ping   # should return: PONG
```

---

### 8.7 Temporal Monitoring (UI)

The **Temporal Web UI** runs at port 8080 and provides:

- Workflow execution history
- Running / failed / timed-out workflows
- Worker status and task queue details

Access via Nginx proxy at:
```
https://postiz.yourdomain.com/temporal/
```

Or directly (if not behind proxy and you're SSH-tunneled):
```bash
# From your local machine:
ssh -L 8080:localhost:8080 root@<YOUR_SERVER_IP>
# Then open: http://localhost:8080
```

**What to monitor:**
- Workflows stuck in **Running** state for > expected duration
- High **Pending** task counts in task queues
- **Failed** workflows (investigate via Temporal UI → Workflow History)

---

### 8.8 Sentry / Spotlight (Error Tracking)

The `spotlight` container runs on port **8969** and is a local Sentry-compatible error inspector.

Access (SSH tunnel from local):
```bash
ssh -L 8969:localhost:8969 root@<YOUR_SERVER_IP>
# Then open: http://localhost:8969
```

> Spotlight captures errors emitted by Postiz during development/debugging. For production error tracking, configure a real Sentry DSN in `.postiz.env`:
>
> ```bash
> SENTRY_DSN=https://your-key@sentry.io/your-project-id
> ```

---

### 8.9 Log Rotation

Docker logs can grow unbounded. Configure log rotation to prevent disk exhaustion.

#### Option A — Per container (in docker-compose.yml)

Add to each service under `postiz` and `temporal`:

```yaml
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

#### Option B — Global Docker daemon config

```bash
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
EOF

systemctl restart docker
```

---

## 9. Backup Strategy

### Automated PostgreSQL backup script

```bash
cat > /opt/postiz/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/opt/postiz/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Dump Postiz DB
docker exec postiz-postgres pg_dump -U postiz-user postiz-db-local \
  | gzip > $BACKUP_DIR/postiz_${TIMESTAMP}.sql.gz

# Dump Temporal DB
docker exec temporal-postgresql pg_dump -U temporal temporal \
  | gzip > $BACKUP_DIR/temporal_${TIMESTAMP}.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup completed: postiz_${TIMESTAMP}.sql.gz"
EOF

chmod +x /opt/postiz/backup.sh
```

### Schedule daily backups with cron

```bash
crontab -e
```

Add:
```
0 3 * * * /opt/postiz/backup.sh >> /var/log/postiz-backup.log 2>&1
```

### Backup uploads volume

```bash
# One-off backup of uploads
docker run --rm \
  -v postiz_postiz-uploads:/data \
  -v /opt/postiz/backups:/backup \
  alpine tar czf /backup/uploads_$(date +%Y%m%d).tar.gz -C /data .
```

---

## 10. Useful Commands Cheatsheet

```bash
# ── Stack management ──────────────────────────────────────────────────────────
docker compose -f /opt/postiz/docker-compose.yml up -d        # start
docker compose -f /opt/postiz/docker-compose.yml down         # stop
docker compose -f /opt/postiz/docker-compose.yml restart      # restart all
docker compose -f /opt/postiz/docker-compose.yml pull && \
  docker compose -f /opt/postiz/docker-compose.yml up -d      # update images

# ── Restart individual service ────────────────────────────────────────────────
docker restart postiz
docker restart postiz-postgres
docker restart postiz-redis
docker restart temporal

# ── View resource usage ───────────────────────────────────────────────────────
docker stats --no-stream
df -h                              # disk usage
free -h                            # memory usage

# ── Logs ─────────────────────────────────────────────────────────────────────
docker logs postiz --tail 200 -f
docker logs temporal --tail 200 -f
journalctl -u nginx -f             # nginx logs

# ── Nginx ─────────────────────────────────────────────────────────────────────
nginx -t                           # test config
systemctl reload nginx             # apply config changes
systemctl status nginx

# ── SSL certificate ───────────────────────────────────────────────────────────
certbot certificates               # view cert expiry
certbot renew --dry-run            # test renewal

# ── Postgres ──────────────────────────────────────────────────────────────────
docker exec -it postiz-postgres psql -U postiz-user -d postiz-db-local

# ── Redis ─────────────────────────────────────────────────────────────────────
docker exec -it postiz-redis redis-cli

# ── Manual DB backup ─────────────────────────────────────────────────────────
/opt/postiz/backup.sh
```

---

## 11. Troubleshooting

### Postiz container keeps restarting

```bash
docker logs postiz --tail 50
```

Common causes:
- `DATABASE_URL` wrong password or host
- `JWT_SECRET` / `NEXTAUTH_SECRET` not set
- Postgres or Redis not yet healthy (check with `docker compose ps`)

### Temporal not starting

```bash
docker logs temporal --tail 100
docker logs temporal-elasticsearch --tail 50
```

OpenSearch takes ~60–90s to start. Temporal will retry automatically. Wait and check again.

### Out of disk space

```bash
df -h
docker system df                   # see Docker disk usage breakdown
docker system prune -f             # remove unused images/containers/networks
docker volume prune -f             # WARNING: removes unused volumes
```

### Nginx 502 Bad Gateway

Means Postiz app is not running or not listening on port 4007:
```bash
docker ps | grep postiz
curl -s http://localhost:4007      # test direct access
```

### PostgreSQL healthcheck failing

```bash
docker exec postiz-postgres pg_isready -U postiz-user -d postiz-db-local
```

If it fails, check logs:
```bash
docker logs postiz-postgres --tail 50
```

---

*Last updated: 2026-02-24*
