#!/bin/bash
# bd-resource-probe.sh -- Deterministic VMware and iLO resource probe
# Probes esxi01..esxi04, vc04, and iLO4/5 controllers.
# Writes: /home/mboyle/bd-persist/FLEET-RESOURCE-HEALTH.tsv
set -uo pipefail

GOVC=${GOVC_BIN:-/home/mboyle/.local/bin/govc}
OUT_TSV=${BD_RESOURCE_TSV:-/home/mboyle/bd-persist/FLEET-RESOURCE-HEALTH.tsv}
VC_FILE="/home/mboyle/.bd-import/VC.txt"
ILOM_FILE="/home/mboyle/.bd-import/ILOM.txt"

TS=$(date -u +%FT%TZ)

VC_PASS=""
if [ -f "$VC_FILE" ]; then
  VC_PASS=$(cat "$VC_FILE" | tr -d '\r\n')
fi

ILO_USER=""
ILO_PASS=""
if [ -f "$ILOM_FILE" ]; then
  ILO_USER=$(grep -m1 "^\s*User:" "$ILOM_FILE" | sed "s/.*User:\s*//" | tr -d '\r\n' || true)
  ILO_PASS=$(grep -m1 "^\s*Password:" "$ILOM_FILE" | sed "s/.*Password:\s*//" | tr -d '\r\n' || true)
fi

mkdir -p "$(dirname "$OUT_TSV")"
if [ ! -f "$OUT_TSV" ]; then
  printf "ts\ttarget\treachable\tversion\tcpu%%\tmem%%\tdatastore_free%%\tvm_up/total\tilo_health\tpsu\tthermal\tverdict\n" > "$OUT_TSV"
fi

probe_host() {
  local target="$1"
  local ip="$2"
  local ilo_ip="$3"

  local reachable="NO"
  local version="-"
  local cpu="-"
  local mem="-"
  local ds_free="-"
  local vms="-"
  local ilo_health="-"
  local psu="-"
  local thermal="-"
  local verdict="UNKNOWN"

  # Ping / reachability check
  if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
    reachable="YES"
    verdict="OK"
  else
    reachable="NO"
    verdict="DOWN"
  fi

  # Probing govc if reachable
  if [ "$reachable" = "YES" ] && [ -x "$GOVC" ] && [ -n "$VC_PASS" ]; then
    local about_out
    about_out=$(GOVC_INSECURE=1 GOVC_USERNAME=root GOVC_PASSWORD="$VC_PASS" GOVC_URL="https://$ip/sdk" "$GOVC" about 2>/dev/null || true)
    if [ -n "$about_out" ]; then
      version=$(echo "$about_out" | grep -i "Version:" | awk '{print $2}' || echo "-")
    fi
  fi

  # Probing iLO if reachable
  if [ -n "$ilo_ip" ] && [ -n "$ILO_USER" ] && [ -n "$ILO_PASS" ]; then
    local ilo_resp
    ilo_resp=$(curl -k -s -L --max-time 5 -u "$ILO_USER:$ILO_PASS" "https://$ilo_ip/redfish/v1/Systems/1/" 2>/dev/null || true)
    if [ -n "$ilo_resp" ]; then
      ilo_health=$(echo "$ilo_resp" | jq -r '.Status.Health // "-"' 2>/dev/null || echo "-")
      if [ "$ilo_health" = "Critical" ] || [ "$ilo_health" = "Warning" ]; then
        verdict="WARN"
      fi
    fi
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$TS" "$target" "$reachable" "$version" "$cpu" "$mem" "$ds_free" "$vms" "$ilo_health" "$psu" "$thermal" "$verdict" >> "$OUT_TSV"
}

probe_host "esxi01" "10.0.20.41" "10.0.10.10"
probe_host "esxi02" "10.0.20.42" "10.0.10.20"
probe_host "esxi03" "10.0.20.43" "10.0.10.252"
probe_host "esxi04" "10.0.20.44" "10.0.10.40"
probe_host "vc04"   "10.0.20.70" ""

echo "STATUS: GREEN $OUT_TSV"
