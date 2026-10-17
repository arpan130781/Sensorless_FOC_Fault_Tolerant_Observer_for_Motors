#!/usr/bin/env python3
"""Sensor-fault robustness sweep for the SIL harness.

For every (fault type, offset size, speed reference, channel, onset phase) it runs the closed loop and
records (a) whether fault_monitor latched the correct phase and (b) whether the OUTCOME is acceptable:
  * ride-through : mean speed within 10 % of the reference, speed p-p <= 450 rpm, angle error <= 45 deg
                   over the last 0.4 s, or
  * safe stop    : SAFE_STOP reached within 1 s of the fault and the motor stopped (< 50 rpm).
Onsets are swept over one electrical period so every current phase is hit. Exit code is non-zero if any
group's acceptable-outcome rate is below --target (default 90 %), so CI / run_all_scenarios.sh can gate on it.
A throw-away debug copy of the C library exports the latch flags (src/ is not modified).

Usage (repo root):
    python3 scripts/isolation_sweep.py                       # defaults: 4 phases, 2000+1500 rpm, 0.5+2.0 A
    python3 scripts/isolation_sweep.py --phases 8 --refs 2000,1500,1000 --offsets 0.5,1.0,2.0
"""
import argparse, ctypes, glob, os, subprocess, sys, tempfile
import numpy as np
from multiprocessing import Pool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

PTP_LIMIT_RPM = 450.0
ANGLE_LIMIT_DEG = 45.0
SPEED_TOL = 0.10
SAFE_MAX_S = 1.0
SAFE_MAX_RPM = 50.0

def build_debug_lib():
    d = tempfile.mkdtemp(prefix='foc_dbg_')
    for f in glob.glob(os.path.join(ROOT, 'src', '*.[ch]')):
        subprocess.check_call(['cp', f, d])
    with open(os.path.join(d, 'foc_core.c'), 'a') as fh:
        fh.write("\nvoid foc_dbg(int* o){o[0]=fault.fault_latch_a;"
                 "o[1]=fault.fault_latch_b;o[2]=fault.fault_latch_c;}\n")
    ext = 'dylib' if sys.platform == 'darwin' else 'so'
    out = os.path.join(d, f'libdbg.{ext}')
    subprocess.check_call(['gcc', '-O2', '-fPIC', '-shared', *glob.glob(d + '/*.c'), '-lm', '-o', out])
    return out

def one(args):
    lib_path, typ, offset, ref, ch, onset = args
    from simulation.harness import config
    config.PATHS['lib_path'] = lib_path
    from simulation.harness.sil_runner import SILRunner
    from simulation.fault_injection.fault_injector import FaultInjector
    p = dict(config.SIM_PARAMS); p['total_time'] = onset + 0.7; p['speed_ref_rpm'] = ref
    r = SILRunner(config_sim=p, fault_scenario='no_fault_baseline')
    sc = {'type': typ, 'channel': ch, 'onset_time': onset}
    if typ == 'sensor_offset':
        sc['offset'] = offset
    r.injector = FaultInjector(sc)
    lib = r.controller.lib; lib.foc_dbg.argtypes = [ctypes.POINTER(ctypes.c_int)]
    buf = (ctypes.c_int * 3)(); first = [None]; orig = r.controller.tick
    def tick(*a):
        out = orig(*a); lib.foc_dbg(buf)
        if first[0] is None and any(buf):
            first[0] = 'abc'[[i for i in range(3) if buf[i]][0]]
        return out
    r.controller.tick = tick
    res = r.run(); w = res.time >= onset + 0.4
    mean = float(res.speed_rpm[w].mean()); ptp = float(np.ptp(res.speed_rpm[w]))
    ang = float(np.max(np.abs(res.angle_error[w])))
    safe = np.where(res.control_mode == 5)[0]
    if len(safe):
        kind = 'safe-stop'
        ok = (res.time[safe[0]] - onset) <= SAFE_MAX_S and abs(float(res.speed_rpm[-1])) < SAFE_MAX_RPM
    else:
        kind = 'ride'
        ok = abs(mean - ref) < SPEED_TOL * ref and ptp <= PTP_LIMIT_RPM and ang <= ANGLE_LIMIT_DEG
    return dict(typ=typ, offset=offset, ref=ref, ch=ch, onset=onset, latched=first[0],
                iso=(first[0] == ch), ok=bool(ok), kind=kind, mean=mean, ptp=ptp, ang=ang)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phases', type=int, default=4, help='onset phases per electrical period')
    ap.add_argument('--refs', default='2000,1500', help='speed references [rpm], comma separated')
    ap.add_argument('--offsets', default='0.5,2.0', help='offset-fault sizes [A], comma separated')
    ap.add_argument('--onsets', default='1.5,2.0', help='base onset times [s]')
    ap.add_argument('--types', default='sensor_stuck,sensor_offset', help='fault types to sweep')
    ap.add_argument('--target', type=float, default=90.0, help='required acceptable-outcome rate [%%]')
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    a = ap.parse_args()
    refs = [float(x) for x in a.refs.split(',')]
    offsets = [float(x) for x in a.offsets.split(',')]
    onsets = [float(x) for x in a.onsets.split(',')]
    types = a.types.split(',')

    lib = build_debug_lib()
    jobs = []
    for ref in refs:
        period = 2 * np.pi / ((ref / 60 * 2 * np.pi) * 4)       # one electrical period at this speed
        phases = [k * period / a.phases for k in range(a.phases)]
        for t0 in onsets:
            for ch in 'abc':
                for ph in phases:
                    if 'sensor_stuck' in types:
                        jobs.append((lib, 'sensor_stuck', 0.0, ref, ch, t0 + ph))
                    if 'sensor_offset' in types:
                        for off in offsets:
                            jobs.append((lib, 'sensor_offset', off, ref, ch, t0 + ph))
    print(f"Running isolation sweep across {len(jobs)} configurations on {a.jobs} workers...", flush=True)
    R = []
    with Pool(a.jobs) as pool:
        for idx, res in enumerate(pool.imap_unordered(one, jobs), 1):
            R.append(res)
            if idx % 12 == 0 or idx == len(jobs):
                print(f"  Progress: {idx}/{len(jobs)} runs completed ({100.0*idx/len(jobs):.1f}%)...", flush=True)

    failed = False
    print(f"\n{len(R)} runs finished\n")
    print(f"{'fault':22s} {'ref':>5s}  {'isolated':>10s}  {'acceptable':>11s}  worst case (ride-through)")
    groups = sorted({(r['typ'], r['offset'], r['ref']) for r in R})
    for typ, off, ref in groups:
        G = [r for r in R if (r['typ'], r['offset'], r['ref']) == (typ, off, ref)]
        iso = sum(r['iso'] for r in G); ok = sum(r['ok'] for r in G)
        rate = 100.0 * ok / len(G)
        name = typ if typ == 'sensor_stuck' else f"{typ} {off:g} A"
        ride = [r for r in G if r['kind'] == 'ride']
        worst = (f"mean {min(r['mean'] for r in ride):.0f} rpm, angle {max(r['ang'] for r in ride):.0f} deg"
                 if ride else "-")
        flag = '' if rate >= a.target else '   <-- BELOW TARGET'
        print(f"{name:22s} {ref:5.0f}  {iso:3d}/{len(G):<3d}({100*iso/len(G):3.0f}%)  {ok:3d}/{len(G):<3d}({rate:3.0f}%)  {worst}{flag}")
        failed |= rate < a.target
    bad = [r for r in R if not r['ok']]
    for r in bad[:12]:
        print(f"  UNACCEPTABLE {r['typ']} off={r['offset']:g} ref={r['ref']:.0f} ch={r['ch']} t0={r['onset']:.4f} "
              f"latched={r['latched']} {r['kind']} mean={r['mean']:.0f} ptp={r['ptp']:.0f} ang={r['ang']:.0f}")
    print(f"\nTarget >= {a.target:g}% acceptable outcomes per group: {'FAILED' if failed else 'MET'}")
    sys.exit(1 if failed else 0)
