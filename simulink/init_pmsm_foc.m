% =========================================================================
% init_pmsm_foc.m
% 
% Initialization script for Sensorless FOC PMSM Simulink Model
% Defines Motor, Inverter, Controller gains, and Fault injection scenarios.
% =========================================================================

fprintf('Initializing Sensorless FOC PMSM parameters...\n');

%% --- 1. PMSM Motor Parameters (100W SPM PMSM) ---
motor.Rs    = 0.5;         % Stator phase resistance (Ohms)
motor.Ls    = 1.0e-3;      % Stator inductance Ld = Lq (Henries)
motor.psi_f = 0.015;       % Permanent magnet flux linkage (Webers)
motor.P     = 4;           % Number of pole pairs
motor.J     = 0.0001;      % Rotor moment of inertia (kg*m^2)
motor.B     = 0.001;       % Viscous friction coefficient (N*m*s/rad)
motor.Vbus  = 24.0;        % DC link bus voltage (Volts)
motor.In    = 5.0;         % Rated peak current (Amperes)
motor.Tcog  = 0.005;       % 6th harmonic cogging torque magnitude (N*m)

% Vector passed to C-MEX S-Function
MotorParamVec = [ ...
    motor.Rs, motor.Ls, motor.psi_f, motor.P, ...
    motor.J,  motor.B,  motor.Vbus,  motor.In ...
];

%% --- 2. Controller & Observer Gains ---
ctrl.id_kp    = 6.28;      % d-axis current PI proportional gain
ctrl.id_ki    = 3142.0;    % d-axis current PI integral gain
ctrl.iq_kp    = 6.28;      % q-axis current PI proportional gain
ctrl.iq_ki    = 3142.0;    % q-axis current PI integral gain
ctrl.spd_kp   = 0.194;     % Speed PI proportional gain
ctrl.spd_ki   = 17.4;      % Speed PI integral gain

ctrl.smo_k    = 20.0;      % Sliding-mode observer sliding gain (V)
ctrl.smo_h    = 0.5;       % SMO sigmoid boundary layer thickness (A)
ctrl.smo_lpf  = 50.0;      % Back-EMF low-pass filter cutoff (rad/s)
ctrl.flux_wc  = 125.6;     % Flux observer crossover frequency (rad/s)
ctrl.pwm_freq = 20000.0;   % PWM frequency & control execution rate (Hz)

% Vector passed to C-MEX S-Function
CtrlParamVec = [ ...
    ctrl.id_kp,  ctrl.id_ki,  ctrl.iq_kp,  ctrl.iq_ki, ...
    ctrl.spd_kp, ctrl.spd_ki, ctrl.smo_k,  ctrl.smo_h, ...
    ctrl.smo_lpf, ctrl.flux_wc, ctrl.pwm_freq ...
];

%% --- 3. Simulation Timing Configuration ---
sim_cfg.Ts_ctrl  = 1.0 / ctrl.pwm_freq; % 50 microseconds (20 kHz discrete controller)
sim_cfg.Ts_plant = 1.0e-5;              % 10 microseconds (100 kHz continuous/ode solver)
sim_cfg.T_final  = 3.0;                 % 3.0 seconds total simulation time

%% --- 4. Operating Profiles & Fault Scenarios ---
% Speed Reference Profile
profile.speed_ref_rpm = 1800.0;         % Target mechanical speed (RPM)

% Load Torque Step
profile.load_step_time = 1.5;           % Step load onset time (s)
profile.load_torque_Nm  = 0.10;          % Load torque step (N*m)

% Sensor Fault Injection Configuration
% Fault Types:
%   0: No fault (baseline)
%   1: DC Sensor Offset (+2.0A on Phase A)
%   2: Sensor Stuck (Frozen at current value)
%   3: High-frequency noise burst
fault.enable       = 1;                 % 1 = Enable fault injection, 0 = Disabled
fault.onset_time   = 2.0;               % Fault onset at t = 2.0 seconds
fault.channel      = 1;                 % 1 = Phase A, 2 = Phase B, 3 = Phase C
fault.type         = 1;                 % Type 1: Sensor offset (+2.0A bias)
fault.offset_val   = 2.0;               % Offset magnitude in Amperes
fault.noise_std    = 0.5;               % Noise standard deviation (for Type 3)

fprintf('Configuration complete.\n');
fprintf('  Motor: 4 Pole Pairs, Rs=%.2f Ohm, Ls=%.3f mH, Vbus=%.1f V\n', ...
    motor.Rs, motor.Ls*1e3, motor.Vbus);
fprintf('  Target Speed: %.1f RPM, Fault Onset: %.2f s on Channel %d\n', ...
    profile.speed_ref_rpm, fault.onset_time, fault.channel);
