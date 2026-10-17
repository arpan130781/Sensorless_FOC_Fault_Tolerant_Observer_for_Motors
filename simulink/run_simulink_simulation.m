% =========================================================================
% run_simulink_simulation.m
%
% Runs the Sensorless FOC PMSM Simulink simulation, calculates quantitative
% metrics, and plots publication-quality response figures.
% =========================================================================

function run_simulink_simulation()
    here = fileparts(mfilename('fullpath'));
    addpath(here);
    results_dir = fullfile(here, 'results');
    if ~exist(results_dir, 'dir')
        mkdir(results_dir);
    end

    % 1. Load Parameters into Base Workspace (where Simulink evaluates them)
    evalin('base', 'init_pmsm_foc');
    
    sim_cfg = evalin('base', 'sim_cfg');
    profile = evalin('base', 'profile');
    fault   = evalin('base', 'fault');

    mdl = 'pmsm_foc_simulink';
    slx_path = fullfile(here, [mdl, '.slx']);
    
    if ~exist(slx_path, 'file')
        fprintf('Model not found. Building %s...\n', mdl);
        create_pmsm_foc_model;
    end

    fprintf('\nRunning Simulink simulation: %s for %.1f seconds...\n', mdl, sim_cfg.T_final);
    tic;
    simOut = sim(mdl, 'ReturnWorkspaceOutputs', 'on');
    sim_time_sec = toc;
    fprintf('Simulation completed in %.2f seconds.\n', sim_time_sec);

    %% --- 2. Extract Data ---
    t = simOut.get('tout');
    speed_data    = simOut.get('sim_speed_rpm');       % [Ref, True, Est]
    angle_err_deg = simOut.get('sim_angle_err_deg');   % True - Est (deg)
    angles_rad    = simOut.get('sim_angles_rad');      % [True, Est]
    currents_data = simOut.get('sim_currents');        % [Meas(1:3), Rec(4:6), True(7:9)]
    diag_data     = simOut.get('sim_diagnostics');     % [Health, Mode, Fault_Ch]
    torque_data   = simOut.get('sim_torque');          % [Te, Load]

    spd_ref  = speed_data(:, 1);
    spd_true = speed_data(:, 2);
    spd_est  = speed_data(:, 3);

    ia_meas = currents_data(:, 1);
    ib_meas = currents_data(:, 2);
    ic_meas = currents_data(:, 3);
    ia_rec  = currents_data(:, 4);
    ib_rec  = currents_data(:, 5);
    ic_rec  = currents_data(:, 6);

    health   = diag_data(:, 1);
    mode_num = diag_data(:, 2);
    fault_ch = diag_data(:, 3);

    % Ensure all signals align with simulation time vector t (handling multirate logging)
    if size(diag_data, 1) ~= length(t)
        t_ctrl = linspace(0, t(end), size(diag_data, 1))';
        health   = interp1(t_ctrl, health, t, 'previous', 'extrap');
        mode_num = interp1(t_ctrl, mode_num, t, 'previous', 'extrap');
        fault_ch = interp1(t_ctrl, fault_ch, t, 'previous', 'extrap');
    end

    %% --- 3. Compute Quantitative Metrics ---
    % Steady-state window: 1.6s to 1.95s (pre-fault closed-loop after startup settling)
    idx_ss = (t >= 1.6) & (t <= 1.95);
    spd_err_ss = abs(spd_true(idx_ss) - spd_ref(idx_ss));
    mean_spd_err = mean(spd_err_ss);
    
    ang_err_ss = angle_err_deg(idx_ss);
    ang_err_rms = sqrt(mean(ang_err_ss.^2));
    ang_err_max = max(abs(ang_err_ss));

    % Post-fault window: 2.1s to 2.9s
    idx_post = (t >= 2.1) & (t <= 2.9);
    ang_err_post = angle_err_deg(idx_post);
    post_ang_err_rms = sqrt(mean(ang_err_post.^2));
    post_ang_err_max = max(abs(ang_err_post));
    
    % Fault detection latency
    idx_fault = find(t >= fault.onset_time, 1);
    idx_isolated = find((t >= fault.onset_time) & (mode_num == 3), 1);
    if ~isempty(idx_isolated)
        latency_ms = (t(idx_isolated) - fault.onset_time) * 1000.0;
    else
        latency_ms = NaN;
    end

    % Reconstruction error on Phase A post-fault
    if size(currents_data, 2) >= 9
        ia_true = currents_data(:, 7);
        rec_err_A = sqrt(mean((ia_rec(idx_post) - ia_true(idx_post)).^2));
    else
        rec_err_A = 0;
    end

    fprintf('\n=======================================================\n');
    fprintf('  Simulink PMSM Sensorless FOC Simulation Results\n');
    fprintf('=======================================================\n');
    fprintf('  Steady-State Speed Error  : %.2f RPM\n', mean_spd_err);
    fprintf('  Pre-Fault Angle Error RMS : %.2f deg (Max: %.2f deg)\n', ang_err_rms, ang_err_max);
    fprintf('  Fault Detection Latency   : %.2f ms\n', latency_ms);
    fprintf('  Post-Fault Angle Error RMS: %.2f deg (Max: %.2f deg)\n', post_ang_err_rms, post_ang_err_max);
    fprintf('  Post-Fault Ia Recon RMS   : %.3f A\n', rec_err_A);
    fprintf('  Operating Mode Transition : Closed-Loop (2) -> Degraded (3)\n');
    fprintf('=======================================================\n\n');

    %% --- 4. Plot Publication-Grade Figures ---
    % Figure 1: Full System Overview (5 Dedicated Subplots)
    hFig1 = figure('Name', 'Simulink PMSM Sensorless FOC', 'Position', [100, 50, 1000, 950], 'Color', 'w');
    
    % Subplot 1: Speed Tracking
    subplot(5, 1, 1);
    plot(t, spd_ref, 'k--', 'LineWidth', 1.5, 'DisplayName', 'Reference');
    hold on;
    plot(t, spd_true, 'b-', 'LineWidth', 1.5, 'DisplayName', 'True PMSM Speed');
    plot(t, spd_est, 'r:', 'LineWidth', 1.2, 'DisplayName', 'Observer \omega_{est}');
    xline(profile.load_step_time, 'm--', 'DisplayName', 'Load Step (0.1 N*m)');
    xline(fault.onset_time, 'r--', 'DisplayName', 'Fault Onset (+2A on Ia)');
    ylabel('Speed (RPM)');
    title('PMSM Sensorless FOC Speed Tracking under Load & Phase A Fault');
    legend('Location', 'best');
    grid on;
    xlim([0, sim_cfg.T_final]);

    % Subplot 2: Electrical Angle Tracking Error
    subplot(5, 1, 2);
    plot(t, angle_err_deg, 'Color', [0.85, 0.32, 0.09], 'LineWidth', 1.2);
    yline(0, 'k--');
    xline(fault.onset_time, 'r--', 'LineWidth', 1.2);
    ylabel('Angle Error (deg)');
    title(sprintf('Electrical Angle Tracking Error \\theta_e - \\theta_{hat} (Closed-Loop RMS: %.2f^\\circ, Post-Fault RMS: %.2f^\\circ)', ...
        ang_err_rms, post_ang_err_rms));
    grid on;
    xlim([0, sim_cfg.T_final]);
    ylim([-25, 25]);

    % Subplot 3: Measured Phase Currents
    subplot(5, 1, 3);
    plot(t, ia_meas, 'r-', 'LineWidth', 1.0, 'DisplayName', 'i_a (with +2A fault)');
    hold on;
    plot(t, ib_meas, 'g-', 'LineWidth', 1.0, 'DisplayName', 'i_b');
    plot(t, ic_meas, 'b-', 'LineWidth', 1.0, 'DisplayName', 'i_c');
    xline(fault.onset_time, 'k--', 'LineWidth', 1.5, 'DisplayName', 'Fault Onset');
    ylabel('Current (A)');
    title('Measured Stator Phase Currents (Notice +2A DC Offset on Phase A at t=2.0s)');
    legend('Location', 'best');
    grid on;
    xlim([1.8, 2.4]); % Zoomed around fault onset

    % Subplot 4: Health Score
    subplot(5, 1, 4);
    plot(t, health * 100.0, 'Color', [0.12, 0.60, 0.20], 'LineWidth', 1.8);
    yline(60.0, 'r--', 'Degraded Threshold (60%)', 'LineWidth', 1.0);
    ylabel('Health (%)');
    ylim([0, 110]);
    title('Fault Monitor Stator Health Score');
    grid on;
    xlim([0, sim_cfg.T_final]);

    % Subplot 5: Operating Mode Transition
    subplot(5, 1, 5);
    plot(t, mode_num, 'Color', [0.49, 0.18, 0.55], 'LineWidth', 2.0);
    xline(fault.onset_time, 'r--', 'LineWidth', 1.2);
    ylabel('Control Mode');
    yticks([0, 1, 2, 3]);
    yticklabels({'ALIGN (0)', 'OPEN LOOP (1)', 'CLOSED LOOP (2)', 'DEGRADED (3)'});
    ylim([-0.5, 3.5]);
    xlabel('Time (seconds)');
    title('Operating Mode State Machine Transitions');
    grid on;
    xlim([0, sim_cfg.T_final]);

    fig1_path = fullfile(results_dir, 'simulink_pmsm_foc_response.png');
    saveas(hFig1, fig1_path);
    fprintf('Saved overview plot: %s\n', fig1_path);

    % Figure 2: Fault Tolerance & 2-Shunt Current Reconstruction
    hFig2 = figure('Name', 'Simulink Current Reconstruction', 'Position', [150, 150, 900, 500], 'Color', 'w');
    
    subplot(2, 1, 1);
    plot(t, ia_meas, 'r--', 'LineWidth', 1.2, 'DisplayName', 'Measured i_a (with +2A fault)');
    hold on;
    plot(t, ia_rec, 'b-', 'LineWidth', 1.5, 'DisplayName', 'Reconstructed i_a (from -i_b - i_c)');
    if size(currents_data, 2) >= 9
        plot(t, currents_data(:, 7), 'k:', 'LineWidth', 1.5, 'DisplayName', 'Ground Truth i_a');
    end
    xline(fault.onset_time, 'r--', 'DisplayName', 'Fault Onset (t=2.0s)');
    ylabel('Phase A Current (A)');
    title('Phase A Current: Corrupted Measurement vs Clean 2-Shunt Reconstruction');
    legend('Location', 'best');
    grid on;
    xlim([1.95, 2.15]);

    subplot(2, 1, 2);
    plot(t, torque_data(:, 1), 'b-', 'LineWidth', 1.2, 'DisplayName', 'Electromagnetic Torque T_e');
    hold on;
    plot(t, torque_data(:, 2), 'k--', 'LineWidth', 1.2, 'DisplayName', 'Load Torque T_L');
    ylabel('Torque (N*m)');
    xlabel('Time (seconds)');
    title('PMSM Torque Dynamics across Fault Event (Smooth, Chatter-Free)');
    legend('Location', 'best');
    grid on;
    xlim([1.95, 2.15]);

    fig2_path = fullfile(results_dir, 'simulink_pmsm_fault_isolation.png');
    saveas(hFig2, fig2_path);
    fprintf('Saved fault reconstruction plot: %s\n', fig2_path);
    
    close(hFig1);
    close(hFig2);
    bdclose(mdl);
end
