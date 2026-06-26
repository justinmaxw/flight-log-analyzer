#!/bin/bash
# Milestone 1 driver: PX4 SITL (SIH quadx) headless, takeoff, then `failure gps off`.
# Feeds timed commands into the pxh> shell via stdin. SIH runs in real-time lockstep,
# so wall-clock sleeps ~= sim seconds.
set -u
cd ~/PX4-Autopilot
export PATH="/Users/justinmaxw/Desktop/flight-log-analyzer/Experiment/.venv/bin:$PATH"
export HEADLESS=1
export PX4_SIM_SPEED_FACTOR=1

# Timeline (wall-clock ~= sim seconds):
#  0s   : boot; wait for EKF + GPS fix
#  20s  : arm + takeoff
#  45s  : (flying ~25s in position control) arm failure injection
#  46s  : record T, then `failure gps off`
#  46-90s: let the no-global-position failsafe play out
#  90s  : shutdown -> flushes the .ulg
{
  sleep 22
  echo "commander takeoff"
  sleep 25
  echo "param set SYS_FAILURE_EN 1"
  sleep 1
  # mark the inject sim-time in the PX4 log stream for exact T recovery
  echo "logger on"
  sleep 1
  echo "==INJECT_GPS_OFF=="
  echo "failure gps off"
  sleep 44
  echo "commander status"
  sleep 2
  echo "shutdown"
  sleep 3
} | make px4_sitl sihsim_quadx
