
import numpy as np

class FaultInjector:
    KNOWN_TYPES = {'none', 'sensor_stuck', 'sensor_stuck_limit', 'sensor_offset', 'noise_burst',
                   'parameter_drift', 'simultaneous'}
    KNOWN_PARAMS = {'Rs', 'Ls'}

    def __init__(self, scenario_config):
        self.config = scenario_config
        self.rng = np.random.default_rng(42)
        self._validate(scenario_config)

    @classmethod
    def _validate(cls, cfg):
        """Fail loudly on unknown scenario types / drift parameters (they used to be silent no-ops)."""
        if not cfg:
            return
        t = cfg.get('type', 'none')
        if t not in cls.KNOWN_TYPES:
            raise ValueError(f"Unknown fault type '{t}' (known: {sorted(cls.KNOWN_TYPES)})")
        if t == 'parameter_drift' and cfg.get('param') not in cls.KNOWN_PARAMS:
            raise ValueError(f"parameter_drift needs param in {sorted(cls.KNOWN_PARAMS)}, got {cfg.get('param')!r}")
        if t == 'simultaneous':
            for f in cfg.get('faults', []):
                cls._validate(f)

    def corrupt_currents(self, ia, ib, ic, t):
        if not self.config: return ia, ib, ic
        # Check specific fault types
        t_type = self.config.get('type')
        if t_type == 'sensor_stuck':
            onset = self.config.get('onset_time', 0.0)
            if t >= onset:
                ch = self.config.get('channel', 'a')
                if not hasattr(self, 'stuck_vals'):
                    self.stuck_vals = {'a': ia, 'b': ib, 'c': ic}
                if ch == 'a': ia = self.stuck_vals['a']
                if ch == 'b': ib = self.stuck_vals['b']
                if ch == 'c': ic = self.stuck_vals['c']
        elif t_type == 'sensor_stuck_limit':
            onset = self.config.get('onset_time', 0.0)
            limit = self.config.get('limit', 10.0)
            if t >= onset:
                ch = self.config.get('channel', 'a')
                if ch == 'a': ia = limit
                if ch == 'b': ib = limit
                if ch == 'c': ic = limit
        elif t_type == 'sensor_offset':
            onset = self.config.get('onset_time', 0.0)
            if t >= onset:
                ch = self.config.get('channel', 'a')
                offset = self.config.get('offset', 0.5)
                if ch == 'a': ia += offset
                if ch == 'b': ib += offset
                if ch == 'c': ic += offset
        elif t_type == 'noise_burst':
            onset = self.config.get('onset_time', 0.0)
            duration = self.config.get('duration', 0.2)
            if onset <= t <= onset + duration:
                mag = self.config.get('magnitude', 0.5) # standard deviation
                ch = self.config.get('channel', 'a')
                if ch == 'a': ia += self.rng.normal(0, mag)
                if ch == 'b': ib += self.rng.normal(0, mag)
                if ch == 'c': ic += self.rng.normal(0, mag)
        elif t_type == 'simultaneous':
            # handle multiple faults by creating temporary single-fault configs
            faults = self.config.get('faults', [])
            for f in faults:
                # We can reuse the main logic by temporarily swapping self.config
                temp_config = self.config
                self.config = f
                # Apply recursively
                ia, ib, ic = self.corrupt_currents(ia, ib, ic, t)
                self.config = temp_config
        
        return ia, ib, ic

    def corrupt_vbus(self, v_bus, t):
        return v_bus
        
    def get_rs_scale(self, t):
        if not self.config: return 1.0
        
        def check_f(f_config):
            if f_config.get('type') == 'parameter_drift' and f_config.get('param') == 'Rs':
                if t >= f_config.get('onset_time', 0.0):
                    return f_config.get('scale', 1.0)
            return 1.0
            
        if self.config.get('type') == 'simultaneous':
            for f in self.config.get('faults', []):
                scale = check_f(f)
                if scale != 1.0: return scale
        else:
            return check_f(self.config)
        return 1.0
        
    def get_ls_scale(self, t):
        if not self.config: return 1.0
        
        def check_f(f_config):
            if f_config.get('type') == 'parameter_drift' and f_config.get('param') == 'Ls':
                if t >= f_config.get('onset_time', 0.0):
                    return f_config.get('scale', 1.0)
            return 1.0
            
        if self.config.get('type') == 'simultaneous':
            for f in self.config.get('faults', []):
                scale = check_f(f)
                if scale != 1.0: return scale
        else:
            return check_f(self.config)
        return 1.0

class NullFaultInjector(FaultInjector):
    def __init__(self):
        super().__init__({})
