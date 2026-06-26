import sys, numpy as np
from pyulog import ULog
u = ULog(sys.argv[1]); T=43.0
def get(name, mid=0):
    for d in u.data_list:
        if d.name==name and d.multi_id==mid: return d
    return None
def t_of(d): return (d.data["timestamp"]-u.start_timestamp)/1e6

# (a) Does the GPS message stop arriving after inject? (dropout = stale stream)
for tp in ("sensor_gps","vehicle_gps_position"):
    d=get(tp); t=t_of(d)
    after=t[t>=T]
    print(f"{tp}: {len(t)} samples, last sample t={t[-1]:.2f}s, "
          f"#samples after inject(T=43)={len(after)}, "
          f"gap between last-pre and first-post-inject = "
          f"{(after[0]-t[t<T][-1]) if len(after) else float('nan'):.2f}s"
          if len(t) else f"{tp}: none")

# (b) onset time of xy_valid flip and test-ratio nan
d=get("vehicle_local_position"); t=t_of(d); xv=d.data["xy_valid"]
flip=t[np.where(np.diff(xv.astype(int))<0)[0]+1]
print(f"\nxy_valid 1->0 at t={flip[0]:.2f}s" if len(flip) else "xy_valid never dropped")
d=get("estimator_status"); t=t_of(d)
for f in ("pos_test_ratio","vel_test_ratio"):
    v=d.data[f]; nant=t[np.isnan(v)]
    print(f"estimator_status.{f}: first NaN at t={nant[0]:.2f}s" if len(nant) else f"{f}: no NaN")

# (c) TRUE divergence: estimate vs groundtruth horizontal position error
est=get("vehicle_local_position"); gt=get("vehicle_local_position_groundtruth")
te=t_of(est); tg=t_of(gt)
def interp(tq, tsrc, vsrc): return np.interp(tq, tsrc, vsrc)
ex=est.data["x"]; ey=est.data["y"]
gx=interp(te, tg, gt.data["x"]); gy=interp(te, tg, gt.data["y"])
err=np.hypot(ex-gx, ey-gy)
print("\nTrue horizontal position error |estimate - groundtruth| (m):")
for ts in (40,43,46,49,52,55,58):
    i=int(np.searchsorted(te,ts)); i=min(i,len(te)-1)
    print(f"   t={ts}s -> {err[i]:.2f} m  (eph={est.data['eph'][i]:.2f})")
print(f"   peak error = {np.nanmax(err[te>=T]):.2f} m")
