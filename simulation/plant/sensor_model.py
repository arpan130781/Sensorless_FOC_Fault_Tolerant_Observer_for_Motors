"""
Sensor Model for phase current sensing:
Implements:
- Bipolar full-scale clipping at +/-full_scale_A
- 12-bit ADC quantization (4096 discrete levels)
- Gaussian noise (noise_rms_A)
- DC offset in LSBs (offset_lsb)
- Startup offset calibration
"""
import numpy as np


class SensorModel:
    def __init__(self, full_scale_A=8.25, bits=12, noise_rms_A=0.030, offset_lsb=20, calibrate_offset=True):
        self.full_scale_A = float(full_scale_A)
        self.bits = bits
        self.max_counts = (1 << bits) - 1  # 4095
        self.noise_rms_A = float(noise_rms_A)
        self.offset_lsb = float(offset_lsb)
        self.calibrate_offset = calibrate_offset
        self.rng = np.random.default_rng(42)

        # Scale factor: Amps per count
        # Bipolar range: -full_scale to +full_scale mapped to 0 .. max_counts
        self.A_per_lsb = (2.0 * self.full_scale_A) / self.max_counts
        self.nominal_zero_count = self.max_counts / 2.0  # 2047.5

    def measure(self, current_A):
        """
        Converts true physical current (Amps) through ADC sensing chain:
        1. Add analog noise
        2. Convert to ADC counts with hardware offset
        3. Clamp to ADC count range [0, max_counts] (clipping)
        4. Quantize to discrete integer counts
        5. Convert back to measured Amps using calibrated offset
        """
        noisy_A = current_A + (self.rng.normal(0.0, self.noise_rms_A) if self.noise_rms_A > 0.0 else 0.0)
        counts = self.nominal_zero_count + (noisy_A / self.A_per_lsb) + self.offset_lsb
        counts_clamped = np.clip(counts, 0.0, self.max_counts)
        quantized_counts = np.round(counts_clamped)

        calibrated_offset = (self.nominal_zero_count + self.offset_lsb) if self.calibrate_offset else self.nominal_zero_count
        measured_A = (quantized_counts - calibrated_offset) * self.A_per_lsb
        return float(measured_A)

    def measure_phases(self, ia, ib, ic):
        return (self.measure(ia), self.measure(ib), self.measure(ic))
