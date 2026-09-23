#!/bin/bash
while true; do
  if tmux capture-pane -t swarm-review-correctness-N2-B -p | tail -n 10 | grep -q 'Do you want to proceed?'; then
    echo "$(date) Unfreezing swarm-review-correctness-N2-B" >> /tmp/auto_approve.log
    tmux send-keys -t swarm-review-correctness-N2-B C-m
  fi
  sleep 2
done
