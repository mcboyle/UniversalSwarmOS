#!/bin/bash
echo "Starting High-Frequency Telemetry Guard..."
while true; do
  /home/mboyle/bd-persist/harness/bd-telemetry-guard.py >> /home/mboyle/bd-persist/logs/telemetry-guard.log 2>&1
  sleep 5
done
