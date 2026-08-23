#!/usr/bin/env bash
# Lock the VPS down to SSH, HTTP and HTTPS. Run once, as root, on the server.
#
#   sudo ./scripts/firewall.sh
#
# Read this before running: it enables a default-deny inbound policy. If your SSH port is
# not 22, pass it as SSH_PORT=2222 ./scripts/firewall.sh, or you will lock yourself out.
#
# Docker note: containers that publish ports write their own iptables rules that bypass
# ufw. This stack publishes nothing except Caddy's 80/443, so that gap is closed by the
# compose configuration rather than by firewall rules — Postgres, Redis, the API and the
# frontend are reachable only on the internal compose network.
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"

[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }

command -v ufw >/dev/null 2>&1 || { echo "==> Installing ufw"; apt-get update -qq && apt-get install -y -qq ufw; }

echo "==> Default deny inbound, allow outbound"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing

echo "==> Allowing SSH on ${SSH_PORT}/tcp (rate limited)"
ufw limit "${SSH_PORT}/tcp" comment 'SSH'

echo "==> Allowing HTTP and HTTPS"
ufw allow 80/tcp  comment 'HTTP (redirect + ACME)'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 443/udp comment 'HTTP/3'

echo "==> Enabling"
ufw --force enable
ufw status verbose

cat <<'NOTE'

==> Confirm from a SECOND terminal that you can still SSH in before closing this one.

    Verify nothing else is listening publicly:
      ss -tulpn | grep -vE '127\.0\.0\.1|::1'

    Only Caddy (80/443) and sshd should appear.
NOTE
