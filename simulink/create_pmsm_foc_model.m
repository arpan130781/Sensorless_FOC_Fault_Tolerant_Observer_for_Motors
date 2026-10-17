% =========================================================================
% create_pmsm_foc_model.m
%
% Programmatically creates and connects the complete Simulink model:
%   pmsm_foc_simulink.slx
%
% Complete Closed-Loop Sensorless FOC Architecture:
%   - Speed Reference & DC Bus
%   - Controller S-Function (Level-2 C-MEX sfun_foc_controller)
%   - 3-Phase PMSM Motor & Inverter S-Function (sfun_pmsm_plant)
%   - Phase A Fault Injector (Offset Step)
%   - Angle Error Calculation with (-180, +180) wrap
%   - Scopes & ToWorkspace Loggers
% =========================================================================

function create_pmsm_foc_model()
    here = fileparts(mfilename('fullpath'));
    addpath(here);
    
    % Initialize variables
    init_pmsm_foc;
    
    mdl = 'pmsm_foc_simulink';
    slx_path = fullfile(here, [mdl, '.slx']);
    
    fprintf('Creating Simulink model: %s...\n', mdl);
    
    if bdIsLoaded(mdl)
        close_system(mdl, 0);
    end
    if exist(slx_path, 'file')
        delete(slx_path);
    end
    
    new_system(mdl);
    load_system('simulink');
    
    % Solver: Fixed-step ode4 (Runge-Kutta 4th order) at 10 us plant rate
    set_param(mdl, ...
        'SolverType', 'Fixed-step', ...
        'Solver', 'ode4', ...
        'FixedStep', num2str(sim_cfg.Ts_plant), ...
        'StopTime', num2str(sim_cfg.T_final), ...
        'SaveTime', 'on', ...
        'TimeSaveName', 'tout', ...
        'SaveOutput', 'off');

    %% --- 1. Sources ---
    add_block('simulink/Sources/Constant', [mdl, '/Speed_Ref'], ...
        'Value', 'profile.speed_ref_rpm', ...
        'Position', [40, 60, 110, 80]);
    
    add_block('simulink/Sources/Constant', [mdl, '/V_bus'], ...
        'Value', 'motor.Vbus', ...
        'Position', [40, 110, 110, 130]);
    
    add_block('simulink/Sources/Step', [mdl, '/Fault_Step_A'], ...
        'Time', 'fault.onset_time', ...
        'Before', '0.0', ...
        'After', 'fault.offset_val * fault.enable', ...
        'SampleTime', '0', ...
        'Position', [40, 220, 110, 240]);
    
    add_block('simulink/Sources/Constant', [mdl, '/Zero_BC'], ...
        'Value', '[0.0; 0.0]', ...
        'Position', [40, 260, 110, 280]);

    add_block('simulink/Sources/Step', [mdl, '/Load_Torque'], ...
        'Time', 'profile.load_step_time', ...
        'Before', '0.0', ...
        'After', 'profile.load_torque_Nm', ...
        'SampleTime', '0', ...
        'Position', [40, 360, 110, 380]);

    %% --- 2. Fault Injection & Signal Routing ---
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Fault'], ...
        'Inputs', '2', ...
        'Position', [140, 225, 145, 275]);

    add_block('simulink/Math Operations/Sum', [mdl, '/Sum_Fault_Inject'], ...
        'Inputs', '++', ...
        'Position', [180, 175, 200, 205]);

    % Mux for FOC Controller Input: [ia, ib, ic, Vbus, speed_ref_rpm]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_FOC_In'], ...
        'Inputs', '3', ...
        'Position', [250, 95, 255, 205]);

    %% --- 3. FOC Controller Block ---
    add_block('simulink/User-Defined Functions/S-Function', [mdl, '/FOC_Controller'], ...
        'FunctionName', 'sfun_foc_controller', ...
        'Parameters', 'MotorParamVec, CtrlParamVec, sim_cfg.Ts_ctrl', ...
        'Position', [290, 120, 460, 180]);

    % Demux for FOC Controller Output (17 signals):
    % [3:duties, 1:theta_hat, 1:spd_hat, 1:health, 1:mode, 3:ia_rec, 1:fault_ch, 2:dq, 2:emf, 2:observers]
    add_block('simulink/Signal Routing/Demux', [mdl, '/Demux_FOC_Out'], ...
        'Outputs', '[3, 1, 1, 1, 1, 3, 1, 2, 2, 2]', ...
        'Position', [490, 60, 495, 240]);

    %% --- 4. PMSM Motor Plant Block ---
    % Mux for Plant Input: [da, db, dc, T_load, Vbus]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Plant_In'], ...
        'Inputs', '3', ...
        'Position', [550, 80, 555, 190]);

    add_block('simulink/User-Defined Functions/S-Function', [mdl, '/PMSM_Motor_Plant'], ...
        'FunctionName', 'sfun_pmsm_plant', ...
        'Parameters', 'MotorParamVec, motor.Tcog', ...
        'Position', [590, 105, 750, 165]);

    % Demux for Plant Output (9 signals):
    % [3:ia_true, 1:theta_e, 1:spd_rpm, 1:omega_e, 1:Te, 2:dq_true]
    add_block('simulink/Signal Routing/Demux', [mdl, '/Demux_Plant_Out'], ...
        'Outputs', '[3, 1, 1, 1, 1, 2]', ...
        'Position', [780, 75, 785, 195]);

    %% --- 5. Angle Error Calculation ---
    add_block('simulink/Math Operations/Sum', [mdl, '/Sum_Angle_Err'], ...
        'Inputs', '+-', ...
        'Position', [830, 240, 850, 260]);

    % Wrap angle difference into (-180, +180) deg using atan2(sin(u), cos(u)) * 180 / pi
    add_block('simulink/User-Defined Functions/Fcn', [mdl, '/Wrap_Angle_Deg'], ...
        'Expr', 'atan2(sin(u), cos(u)) * 180 / pi', ...
        'Position', [880, 235, 1020, 265]);

    %% --- 6. Muxes for Data Logging ---
    % Speeds: [Ref, True, Est]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Speed_Log'], ...
        'Inputs', '3', ...
        'Position', [880, 40, 885, 100]);

    % Angles: [True, Est]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Angle_Log'], ...
        'Inputs', '2', ...
        'Position', [880, 140, 885, 190]);

    % Currents: [Meas(3), Rec(3), True(3)]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Currents_Log'], ...
        'Inputs', '3', ...
        'Position', [380, 310, 385, 380]);

    % Diagnostics: [Health, Mode, Fault_Channel]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Diag_Log'], ...
        'Inputs', '3', ...
        'Position', [600, 260, 605, 320]);

    % Torque: [Te_actual, T_load]
    add_block('simulink/Signal Routing/Mux', [mdl, '/Mux_Torque_Log'], ...
        'Inputs', '2', ...
        'Position', [880, 310, 885, 350]);

    %% --- 7. To Workspace Logging Blocks ---
    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Speed'], ...
        'VariableName', 'sim_speed_rpm', ...
        'SaveFormat', 'Array', ...
        'Position', [920, 55, 1010, 85]);

    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Angle_Err'], ...
        'VariableName', 'sim_angle_err_deg', ...
        'SaveFormat', 'Array', ...
        'Position', [1050, 235, 1140, 265]);

    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Angles'], ...
        'VariableName', 'sim_angles_rad', ...
        'SaveFormat', 'Array', ...
        'Position', [920, 150, 1010, 180]);

    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Currents'], ...
        'VariableName', 'sim_currents', ...
        'SaveFormat', 'Array', ...
        'Position', [420, 330, 510, 360]);

    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Diagnostics'], ...
        'VariableName', 'sim_diagnostics', ...
        'SaveFormat', 'Array', ...
        'Position', [640, 275, 730, 305]);

    add_block('simulink/Sinks/To Workspace', [mdl, '/To_WS_Torque'], ...
        'VariableName', 'sim_torque', ...
        'SaveFormat', 'Array', ...
        'Position', [920, 315, 1010, 345]);

    %% --- 8. Scopes for Real-Time Visualization ---
    add_block('simulink/Sinks/Scope', [mdl, '/Scope_Speed_Tracking'], ...
        'Position', [1040, 55, 1080, 85]);

    add_block('simulink/Sinks/Scope', [mdl, '/Scope_Angle_Error'], ...
        'Position', [1170, 235, 1210, 265]);

    add_block('simulink/Sinks/Scope', [mdl, '/Scope_Phase_Currents'], ...
        'Position', [540, 330, 580, 360]);

    add_block('simulink/Sinks/Scope', [mdl, '/Scope_Diagnostics'], ...
        'Position', [760, 275, 800, 305]);

    %% --- 9. Wiring & Interconnections ---
    % Fault Mux
    add_line(mdl, 'Fault_Step_A/1', 'Mux_Fault/1', 'autorouting', 'on');
    add_line(mdl, 'Zero_BC/1', 'Mux_Fault/2', 'autorouting', 'on');

    % Fault Sum: Plant True Currents + Fault Offset
    add_line(mdl, 'Demux_Plant_Out/1', 'Sum_Fault_Inject/1', 'autorouting', 'on');
    add_line(mdl, 'Mux_Fault/1', 'Sum_Fault_Inject/2', 'autorouting', 'on');

    % Controller Input Mux: [I_meas, Vbus, Speed_Ref]
    add_line(mdl, 'Sum_Fault_Inject/1', 'Mux_FOC_In/1', 'autorouting', 'on');
    add_line(mdl, 'V_bus/1', 'Mux_FOC_In/2', 'autorouting', 'on');
    add_line(mdl, 'Speed_Ref/1', 'Mux_FOC_In/3', 'autorouting', 'on');

    % Connect Controller S-Function
    add_line(mdl, 'Mux_FOC_In/1', 'FOC_Controller/1', 'autorouting', 'on');
    add_line(mdl, 'FOC_Controller/1', 'Demux_FOC_Out/1', 'autorouting', 'on');

    % Plant Input Mux: [Duties, T_load, Vbus]
    add_line(mdl, 'Demux_FOC_Out/1', 'Mux_Plant_In/1', 'autorouting', 'on');
    add_line(mdl, 'Load_Torque/1', 'Mux_Plant_In/2', 'autorouting', 'on');
    add_line(mdl, 'V_bus/1', 'Mux_Plant_In/3', 'autorouting', 'on');

    % Connect Plant S-Function
    add_line(mdl, 'Mux_Plant_In/1', 'PMSM_Motor_Plant/1', 'autorouting', 'on');
    add_line(mdl, 'PMSM_Motor_Plant/1', 'Demux_Plant_Out/1', 'autorouting', 'on');

    % Speed Mux & Log: [Ref, True, Est]
    add_line(mdl, 'Speed_Ref/1', 'Mux_Speed_Log/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_Plant_Out/3', 'Mux_Speed_Log/2', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/3', 'Mux_Speed_Log/3', 'autorouting', 'on');
    add_line(mdl, 'Mux_Speed_Log/1', 'To_WS_Speed/1', 'autorouting', 'on');
    add_line(mdl, 'Mux_Speed_Log/1', 'Scope_Speed_Tracking/1', 'autorouting', 'on');

    % Angles Mux & Angle Error
    add_line(mdl, 'Demux_Plant_Out/2', 'Mux_Angle_Log/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/2', 'Mux_Angle_Log/2', 'autorouting', 'on');
    add_line(mdl, 'Mux_Angle_Log/1', 'To_WS_Angles/1', 'autorouting', 'on');

    add_line(mdl, 'Demux_Plant_Out/2', 'Sum_Angle_Err/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/2', 'Sum_Angle_Err/2', 'autorouting', 'on');
    add_line(mdl, 'Sum_Angle_Err/1', 'Wrap_Angle_Deg/1', 'autorouting', 'on');
    add_line(mdl, 'Wrap_Angle_Deg/1', 'To_WS_Angle_Err/1', 'autorouting', 'on');
    add_line(mdl, 'Wrap_Angle_Deg/1', 'Scope_Angle_Error/1', 'autorouting', 'on');

    % Currents Log: [I_meas, I_rec, I_true]
    add_line(mdl, 'Sum_Fault_Inject/1', 'Mux_Currents_Log/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/6', 'Mux_Currents_Log/2', 'autorouting', 'on');
    add_line(mdl, 'Demux_Plant_Out/1', 'Mux_Currents_Log/3', 'autorouting', 'on');
    add_line(mdl, 'Mux_Currents_Log/1', 'To_WS_Currents/1', 'autorouting', 'on');
    add_line(mdl, 'Mux_Currents_Log/1', 'Scope_Phase_Currents/1', 'autorouting', 'on');

    % Diagnostics Log: [Health, Mode, Fault_Ch]
    add_line(mdl, 'Demux_FOC_Out/4', 'Mux_Diag_Log/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/5', 'Mux_Diag_Log/2', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/7', 'Mux_Diag_Log/3', 'autorouting', 'on');
    add_line(mdl, 'Mux_Diag_Log/1', 'To_WS_Diagnostics/1', 'autorouting', 'on');
    add_line(mdl, 'Mux_Diag_Log/1', 'Scope_Diagnostics/1', 'autorouting', 'on');

    % Torque Log: [Te, T_load]
    add_line(mdl, 'Demux_Plant_Out/5', 'Mux_Torque_Log/1', 'autorouting', 'on');
    add_line(mdl, 'Load_Torque/1', 'Mux_Torque_Log/2', 'autorouting', 'on');
    add_line(mdl, 'Mux_Torque_Log/1', 'To_WS_Torque/1', 'autorouting', 'on');

    % Terminators for unused diagnostic ports
    add_block('simulink/Sinks/Terminator', [mdl, '/Term_FOC_8'], 'Position', [540, 190, 560, 200]);
    add_block('simulink/Sinks/Terminator', [mdl, '/Term_FOC_9'], 'Position', [540, 210, 560, 220]);
    add_block('simulink/Sinks/Terminator', [mdl, '/Term_FOC_10'], 'Position', [540, 230, 560, 240]);
    add_line(mdl, 'Demux_FOC_Out/8', 'Term_FOC_8/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/9', 'Term_FOC_9/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_FOC_Out/10', 'Term_FOC_10/1', 'autorouting', 'on');

    add_block('simulink/Sinks/Terminator', [mdl, '/Term_Plant_4'], 'Position', [830, 140, 850, 150]);
    add_block('simulink/Sinks/Terminator', [mdl, '/Term_Plant_6'], 'Position', [830, 180, 850, 190]);
    add_line(mdl, 'Demux_Plant_Out/4', 'Term_Plant_4/1', 'autorouting', 'on');
    add_line(mdl, 'Demux_Plant_Out/6', 'Term_Plant_6/1', 'autorouting', 'on');

    % Save model
    save_system(mdl, slx_path);
    close_system(mdl);
    
    fprintf('Successfully built and saved %s!\n', slx_path);
end
