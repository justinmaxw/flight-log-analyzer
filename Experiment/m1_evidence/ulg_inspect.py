import sys, numpy as np
from pyulog import ULog

ulg = sys.argv[1]
T = 43.0  # inject sim-time (s) from event log

u = ULog(ulg)
names = sorted({d.name for d in u.data_list})

# 1) Confirm exact topic names actually present
def has(n): return n in names
print("=== topics present (gps / estimator / position) ===")
for n in names:
    if any(k in n for k in ("gps","estimator","local_position","global_position","vehicle_status")):
        print("  ", n)

def get(name):
    for d in u.data_list:
        if d.name == name and d.multi_id == 0:
            return d
    return None

def t_of(d):
    return (d.data["timestamp"] - u.start_timestamp) / 1e6

def near(d, field, ts):
    t = t_of(d); v = d.data[field]
    i = int(np.searchsorted(t, ts))
    i = min(max(i,0), len(t)-1)
    return t[i], v[i]

def show(topic, field, label):
    d = get(topic)
    if d is None or field not in d.data:
        print(f"   [{topic}.{field}] NOT FOUND"); return
    print(f"   {label}  ({topic}.{field})")
    for ts in (T-5, T-1, T+1, T+3, T+6, T+10):
        try:
            tt, vv = near(d, field, ts)
            print(f"      t={ts:5.1f}s -> {vv}")
        except Exception as e:
            print(f"      t={ts:5.1f}s -> err {e}")

print("\n=== 2) GPS dropout ===")
gps_topic = "vehicle_gps_position" if has("vehicle_gps_position") else ("sensor_gps" if has("sensor_gps") else None)
if gps_topic:
    d = get(gps_topic)
    for f in ("fix_type","satellites_used","s_variance_m_s"):
        if f in d.data: show(gps_topic, f, "GPS")

print("\n=== 3) Estimator innovation test ratios ===")
for cand in ("estimator_innovation_test_ratios","estimator_status"):
    if has(cand):
        d = get(cand)
        for f in ("gps_hvel","gps_vvel","gps_hpos","gps_vpos","vel_test_ratio","pos_test_ratio","hgt_test_ratio"):
            if f in d.data: show(cand, f, "test_ratio")

print("\n=== 4) estimator_status flags / GPS check ===")
if has("estimator_status"):
    d=get("estimator_status")
    for f in ("gps_check_fail_flags","health_flags","timeout_flags","control_mode_flags","filter_fault_flags"):
        if f in d.data: show("estimator_status","gps_check_fail_flags" if f=="gps_check_fail_flags" else f, f)

print("\n=== 5) Position estimate validity / divergence ===")
if has("vehicle_local_position"):
    d=get("vehicle_local_position")
    for f in ("xy_valid","v_xy_valid","eph","epv","x","y","vx","vy"):
        if f in d.data: show("vehicle_local_position", f, "local_pos")
