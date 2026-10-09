
import numpy as np

def compute_angle_error_rms(result, start_time=None, end_time=None) -> float:
    mask = _get_mask(result, start_time, end_time)
    if not np.any(mask): return 0.0
    return float(np.sqrt(np.mean(result.angle_error[mask]**2)))

def compute_max_angle_error(result, start_time=None, end_time=None) -> float:
    mask = _get_mask(result, start_time, end_time)
    if not np.any(mask): return 0.0
    return float(np.max(np.abs(result.angle_error[mask])))

def compute_detection_latency(result, fault_onset_time) -> dict:
    post_fault = result.time >= fault_onset_time
    idx = np.where(result.control_mode[post_fault] >= 3)[0] # DEGRADED or higher
    
    # Calculate separate timestamps
    latency_ms = -1.0
    if len(idx) > 0:
        latency_ms = float((result.time[post_fault][idx[0]] - fault_onset_time) * 1000.0)
        
    return {
        'latency_ms': latency_ms,
        'detected': latency_ms >= 0
    }

def compute_speed_tracking_error(result, ref_speed=2000.0, start_time=None, end_time=None):
    mask = _get_mask(result, start_time, end_time)
    if not np.any(mask): return {'rms': 0.0, 'max': 0.0, 'steady_state': 0.0}
    err = result.speed_rpm[mask] - ref_speed
    return {
        'rms': float(np.sqrt(np.mean(err**2))),
        'max': float(np.max(np.abs(err))),
        'steady_state': float(np.mean(np.abs(err[-1000:])))
    }

def compute_settling_time(result, ref_speed=2000.0, threshold_pct=5.0) -> float:
    threshold = abs(ref_speed) * (threshold_pct / 100.0)
    err = np.abs(result.speed_rpm - ref_speed)
    # Find the first point after which the speed remains within the specified tolerance
    # for the remainder of the evaluation window.
    # unsettled points
    unsettled = np.where(err > threshold)[0]
    if len(unsettled) == 0:
        return 0.0
    
    last_unsettled_idx = unsettled[-1]
    if last_unsettled_idx == len(err) - 1:
        # Never settled
        return float('inf')
        
    return float(result.time[last_unsettled_idx + 1])

def compute_current_reconstruction_error(result, fault_onset_time) -> dict:
    post_fault = result.time >= fault_onset_time
    if not np.any(post_fault): return {'rms': 0.0, 'max': 0.0}
    
    # Calculate difference between reconstructed currents and true currents
    err_a = result.i_a_rec[post_fault] - result.i_true_a[post_fault]
    err_b = result.i_b_rec[post_fault] - result.i_true_b[post_fault]
    err_c = result.i_c_rec[post_fault] - result.i_true_c[post_fault]
    
    # Find the maximum RMS across the three phases
    rms_a = float(np.sqrt(np.mean(err_a**2)))
    rms_b = float(np.sqrt(np.mean(err_b**2)))
    rms_c = float(np.sqrt(np.mean(err_c**2)))
    max_a = float(np.max(np.abs(err_a)))
    max_b = float(np.max(np.abs(err_b)))
    max_c = float(np.max(np.abs(err_c)))
    
    return {
        'rms': max(rms_a, rms_b, rms_c),
        'max': max(max_a, max_b, max_c)
    }
    
def evaluate_scenario(result, criteria_dict, fault_onset_time=float('inf'), ref_speed=2000.0, start_time=None, expected_fault_channel=0, expected_mode_after_fault=3):
    out = {}
    mask = _get_mask(result, start_time, None)
    
    for crit, limit in criteria_dict.items():
        if crit == 'max_angle_error':
            val = compute_max_angle_error(result, start_time)
            out[crit] = {'pass': val <= limit, 'value': val}
        elif crit == 'angle_error_rms':
            val = compute_angle_error_rms(result, start_time)
            out[crit] = {'pass': val <= limit, 'value': val}
        elif crit == 'speed_ripple_ptp':
            ptp = np.ptp(result.speed_rpm[mask])
            out[crit] = {'pass': ptp <= limit, 'value': ptp}
        elif crit == 'settling_time':
            val = compute_settling_time(result, ref_speed=ref_speed)
            out[crit] = {'pass': val <= limit, 'value': val}
        elif crit == 'mean_speed':
            end_mask = _get_mask(result, start_time, None)
            mean_speed = float(np.mean(result.speed_rpm[end_mask]))
            # Evaluate the absolute error! Limit is the maximum allowed error
            err = abs(mean_speed - ref_speed)
            passed = err <= limit
            out[crit] = {'pass': passed, 'value': err}
        elif crit == 'detection_latency':
            if fault_onset_time < float('inf'):
                metrics = compute_detection_latency(result, fault_onset_time)
                val = metrics['latency_ms']
                passed = (0 <= val <= limit)
                out[crit] = {'pass': passed, 'value': val}
        elif crit == 'fault_isolation':
            if fault_onset_time < float('inf'):
                # Check what channel was isolated in the post-fault steady state
                post_fault = result.time >= fault_onset_time + 0.1 # wait 100ms
                modes = result.fault_channel[post_fault]
                if len(modes) > 0:
                    isolated = modes[-1]
                else:
                    isolated = 0
                passed = (isolated == expected_fault_channel)
                out[crit] = {'pass': passed, 'value': isolated}
        
        elif crit == 'reconstruction_error_rms':
            if fault_onset_time < float('inf'):
                err_dict = compute_current_reconstruction_error(result, fault_onset_time)
                val = err_dict['rms']
                passed = val <= limit
                out[crit] = {'pass': passed, 'value': val}
        elif crit == 'recovery_time':
            if fault_onset_time < float('inf'):
                # find when we return to mode 2 (CLOSED_LOOP) after fault_onset_time
                post_fault = result.time >= fault_onset_time
                mode_post = result.control_mode[post_fault]
                time_post = result.time[post_fault]
                
                # We expect to enter mode 3 (DEGRADED)
                degraded_idx = np.where(mode_post >= 3)[0]
                if len(degraded_idx) > 0:
                    t_degraded = time_post[degraded_idx[0]]
                    # Then back to mode 2
                    recovered_idx = np.where((time_post > t_degraded) & (mode_post == 2))[0]
                    if len(recovered_idx) > 0:
                        t_recovered = time_post[recovered_idx[0]]
                        # the noise burst duration is 0.1s
                        # So fault ends at fault_onset_time + 0.1
                        # Recovery should happen within `limit` after the fault ends
                        val = t_recovered - (fault_onset_time + 0.1)
                        passed = 0 <= val <= limit
                    else:
                        val = -1.0
                        passed = False
                else:
                    val = -1.0
                    passed = False
                out[crit] = {'pass': passed, 'value': val}
        elif crit == 'safe_stop_time':
            if fault_onset_time < float('inf'):
                post_fault = result.time >= fault_onset_time
                safe_stop_idx = np.where(result.control_mode[post_fault] == 5)[0]
                if len(safe_stop_idx) > 0:
                    val = float((result.time[post_fault][safe_stop_idx[0]] - fault_onset_time) * 1000.0)
                    passed = val <= limit
                else:
                    val = -1.0
                    passed = False
                out[crit] = {'pass': passed, 'value': val}
                
    # Also evaluate if we reached the expected mode (e.g. SAFE_STOP = 5, DEGRADED = 3)
    # Always evaluate expected mode if it's provided in the YAML criteria.
    final_mode = result.control_mode[-1]
    out['expected_mode'] = {'pass': (final_mode == expected_mode_after_fault), 'value': final_mode}

    return out

def _get_mask(res, start, end):
    t = res.time
    mask = np.ones_like(t, dtype=bool)
    if start is not None: mask &= (t >= start)
    if end is not None: mask &= (t <= end)
    return mask
