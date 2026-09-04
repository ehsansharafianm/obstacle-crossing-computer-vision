clc
clear all
close all
addpath(fileparts(mfilename('fullpath')));

% PLOT_TRAJECTORY (script)  Interactive 3D + X/Y/Z-vs-time plot of marker
% trajectories, styled for presentation (Arial, bold labels, thick lines/box),
% with per-marker toggles. Run it and enter the test NUMBER at the prompt (e.g. 22)
% -> results/sessions/testN/testN_trajectory.xlsx (falls back to .csv).
%
% Reads the marker trajectories (a .xlsx "markers" sheet, or a plain .csv):
%   time_s, <marker>_x_mm, <marker>_y_mm, <marker>_z_mm, ...
% Any number of markers is supported (names auto-detected from the headers).
% Markers named obstacle* are drawn as scatter POINTS (quasi-static); feet as lines.
%
% Line/point colours MATCH each physical marker (purple toe, green heel, pink/teal
% right foot, red obstacle) so the plots read like the real setup.
%
% Opens up to THREE figures: (1) the 3D trajectory, (2) X / Y / Z vs time, and
% (3) the audio clap-sync (if the .xlsx has an 'audio' sheet). Re-running closes
% the previous set first. Controls:
%   * one checkbox per marker  -> on BOTH the 3D figure (stacked, top-left) AND the
%                                 positions-vs-time figure (a row across the top);
%                                 either hides/shows the marker in every panel.
%   * Line / Scatter dropdown (3D figure) -> switch the feet between line and points
%                                 (obstacle markers stay scatter points).

    % ===================== STYLE (edit here) =====================
    S.font    = 'Arial';   % font family
    S.xlbl    = 25;        % x-axis label size
    S.ylbl    = 25;        % y/z-axis label size
    S.tick    = 20;        % axis tick-number size
    S.title   = 22;        % title size
    S.legend  = 16;        % legend size
    S.trajLW  = 2.5;       % trajectory line width
    S.boxLW   = 2;         % axis box border width
    S.footPt  = 8;         % foot scatter point size (Scatter mode)
    S.obstPt  = 16;        % obstacle scatter point size
    % =============================================================

    % Enter the test number at the prompt -> results/sessions/testN/testN_trajectory.xlsx
    tn = input('  Input Test Number: ');
    id = ['test' num2str(tn)];
    root  = fileparts(fileparts(mfilename('fullpath')));      % repo root
    candx = fullfile(root, 'results', 'sessions', id, [id '_trajectory.xlsx']);
    candc = fullfile(root, 'results', 'sessions', id, [id '_trajectory.csv']);
    if exist(candx, 'file'),     datafile = candx;
    elseif exist(candc, 'file'), datafile = candc;
    else,  error('No trajectory file for "%s". Looked for:\n  %s\n  %s', id, candx, candc);
    end
    isxlsx = endsWith(lower(datafile), '.xlsx');

    % --- close any previous window opened by this function ---
    delete(findall(0, 'Type', 'figure', 'Tag', 'trajfig'));

    if isxlsx
        T = readtable(datafile, 'Sheet', 'markers');
    else
        T = readtable(datafile);
    end
    vn = T.Properties.VariableNames;
    if ~ismember('time_s', vn), error('File must have a "time_s" column.'); end
    t = T.time_s;

    % --- auto-detect marker names from "<name>_x_mm" columns ---
    markers = {};
    for i = 1:numel(vn)
        tok = regexp(vn{i}, '^(.*)_x_mm$', 'tokens', 'once');
        if ~isempty(tok), markers{end+1} = tok{1}; end %#ok<AGROW>
    end
    nM = numel(markers);
    if nM == 0, error('No "<marker>_x_mm" columns found.'); end
    cmap = lines(max(nM, 3));      % fallback for unrecognised marker names
    mcol = zeros(nM, 3);           % actual per-marker colours (filled in the plot loop)

    % --- Figure 1: the 3D trajectory (carries the marker/obstacle toggles) ---
    fig3 = figure('Name', 'Marker trajectories - 3D', 'Color', 'w', ...
                  'Tag', 'trajfig', 'Position', [70 120 780 720]);
    ax3 = axes('Parent', fig3, 'Position', [0.15 0.11 0.80 0.80]);
    hold(ax3, 'on'); grid(ax3, 'on'); box(ax3, 'on');
    xlabel(ax3, 'X (mm)', 'FontSize', S.xlbl, 'FontName', S.font, 'FontWeight', 'bold');
    ylabel(ax3, 'Y (mm)', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
    zlabel(ax3, 'Z (mm)', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
    title(ax3, '3D trajectory', 'FontSize', S.title, 'FontName', S.font, 'FontWeight', 'bold');
    view(ax3, 3); axis(ax3, 'equal'); rotate3d(ax3, 'on');

    % --- Figure 2: X / Y / Z vs time ---
    figp = figure('Name', 'Marker positions vs time', 'Color', 'w', ...
                  'Tag', 'trajfig', 'Position', [860 120 700 720]);
    axX = axes('Parent', figp, 'Position', [0.15 0.66 0.80 0.22]); prep(axX);
    ylabel(axX, 'X (mm)', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
    title(axX, 'Position vs time', 'FontSize', S.title, 'FontName', S.font, 'FontWeight', 'bold');
    axY = axes('Parent', figp, 'Position', [0.15 0.39 0.80 0.22]); prep(axY);
    ylabel(axY, 'Y (mm)', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
    axZ = axes('Parent', figp, 'Position', [0.15 0.10 0.80 0.22]); prep(axZ);
    xlabel(axZ, 'time (s)', 'FontSize', S.xlbl, 'FontName', S.font, 'FontWeight', 'bold');
    ylabel(axZ, 'Z (mm)', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');

    % --- plot each marker: feet as connected trajectories; obstacle* markers as
    %     scatter POINTS (kept as points regardless of the Line/Scatter toggle) ---
    H = containers.Map();
    isObstacle = containers.Map();
    for k = 1:nM
        m = markers{k}; c = markerColor(m, k, cmap); mcol(k, :) = c;
        x = T.([m '_x_mm']); y = T.([m '_y_mm']); z = T.([m '_z_mm']);
        obs = startsWith(m, 'obstacle'); isObstacle(m) = obs;
        if obs, ls = 'none'; mk = '.'; ms = S.obstPt; else, ls = '-'; mk = 'none'; ms = S.footPt; end
        h = gobjects(1, 4);
        h(1) = plot3(ax3, x, y, z, 'Color', c, 'LineStyle', ls, 'Marker', mk, ...
                     'MarkerSize', ms, 'LineWidth', S.trajLW, 'DisplayName', m);
        h(2) = plot(axX, t, x, 'Color', c, 'LineStyle', ls, 'Marker', mk, 'MarkerSize', ms, 'LineWidth', S.trajLW);
        h(3) = plot(axY, t, y, 'Color', c, 'LineStyle', ls, 'Marker', mk, 'MarkerSize', ms, 'LineWidth', S.trajLW);
        h(4) = plot(axZ, t, z, 'Color', c, 'LineStyle', ls, 'Marker', mk, 'MarkerSize', ms, 'LineWidth', S.trajLW);
        H(m) = h;
    end

    % --- overlay a legacy static OBSTACLE sheet ('obstacle' or old 'ground'), if any ---
    gh = gobjects(0);
    if isxlsx
        try
            sh = sheetnames(datafile);
            osheet = '';
            if any(strcmp(sh, 'obstacle')),   osheet = 'obstacle';
            elseif any(strcmp(sh, 'ground')), osheet = 'ground';
            end
            if ~isempty(osheet)
                G = readtable(datafile, 'Sheet', osheet);
                gh = plot3(ax3, G.x_mm, G.y_mm, G.z_mm, 's', 'Color', [0.85 0.12 0.12], ...
                      'LineWidth', 1.6, 'MarkerSize', S.obstPt, 'MarkerFaceColor', [0.85 0.12 0.12], ...
                      'MarkerEdgeColor', 'k', 'DisplayName', 'obstacle');
            end
        catch
        end
    end
    lg = legend(ax3, 'show', 'Location', 'best', 'Interpreter', 'none');
    lg.FontSize = S.legend; lg.FontName = S.font;

    % --- set time axes to the data range, THEN link (order matters) ---
    tv = t(any(~isnan(T{:, 2:end}), 2));           % times with any marker data
    if ~isempty(tv), xlim(axX, [min(tv) max(tv)]); end
    arrayfun(@(a) axis(a, 'auto y'), [axX axY axZ]);
    linkaxes([axX axY axZ], 'x');

    % --- apply the shared publication styling to every data axis ---
    for ax = [ax3 axX axY axZ]
        set(ax, 'FontName', S.font, 'FontSize', S.tick, 'FontWeight', 'bold', ...
            'LineWidth', S.boxLW, 'Box', 'on');
    end

    % --- per-marker on/off checkboxes on the 3D figure (top-left, stacked) ---
    for k = 1:nM
        m = markers{k};
        uicontrol(fig3, 'Style', 'checkbox', 'String', m, 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.030*(k-1) 0.16 0.028], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', mcol(k, :), ...
            'Callback', @(src, ~) set(H(m), 'Visible', onoff(src.Value)));
    end

    % --- the SAME toggles on the positions-vs-time figure (a row across the top),
    %     so markers can be shown/hidden from either window (both drive H(m)) ---
    cbw = min(0.80 / nM, 0.16);
    for k = 1:nM
        m = markers{k};
        uicontrol(figp, 'Style', 'checkbox', 'String', m, 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.15+cbw*(k-1) 0.94 cbw 0.035], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', mcol(k, :), ...
            'Callback', @(src, ~) set(H(m), 'Visible', onoff(src.Value)));
    end

    % --- obstacle (legacy static overlay) on/off checkbox ---
    nRows = nM;
    if ~isempty(gh)
        uicontrol(fig3, 'Style', 'checkbox', 'String', 'obstacle', 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.030*nM 0.16 0.028], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', [0.85 0.12 0.12], ...
            'Callback', @(src, ~) set(gh, 'Visible', onoff(src.Value)));
        nRows = nM + 1;
    end

    % --- Line / Scatter style dropdown (feet only; obstacle stays scatter) ---
    uicontrol(fig3, 'Style', 'text', 'String', 'style:', 'Units', 'normalized', ...
        'Position', [0.05 0.955-0.030*nRows-0.03 0.05 0.026], 'BackgroundColor', 'w', ...
        'HorizontalAlignment', 'left');
    uicontrol(fig3, 'Style', 'popupmenu', 'String', {'Line', 'Scatter'}, ...
        'Units', 'normalized', 'Position', [0.10 0.955-0.030*nRows-0.03 0.11 0.028], ...
        'Callback', @(src, ~) setstyle(H, src.Value, isObstacle, S));

    % --- Figure 3: the audio clap sync for ALL cameras (needs an 'audio' sheet) --
    if isxlsx && any(strcmp(sheetnames(datafile), 'audio'))
        A = readtable(datafile, 'Sheet', 'audio'); ta = A.time_s;
        figa = figure('Name', 'Audio clap sync', 'Color', 'w', ...
                      'Tag', 'trajfig', 'Position', [200 90 940 560]);
        cams = {'cam1', 'cam2', 'cam3'};
        cc = [0.12 0.47 0.71; 0.84 0.19 0.42; 0.17 0.63 0.17];
        axa1 = subplot(2, 1, 1, 'Parent', figa); hold(axa1, 'on'); grid(axa1, 'on');
        axa2 = subplot(2, 1, 2, 'Parent', figa); hold(axa2, 'on'); grid(axa2, 'on');
        leg = {};
        for i = 1:numel(cams)
            raw = [cams{i} '_env']; aln = [cams{i} '_env_aligned'];
            if ismember(raw, A.Properties.VariableNames)
                plot(axa1, ta, A.(raw), 'Color', cc(i, :), 'LineWidth', S.trajLW);
                plot(axa2, ta, A.(aln), 'Color', cc(i, :), 'LineWidth', S.trajLW);
                leg{end+1} = cams{i}; %#ok<AGROW>
            end
        end
        title(axa1, 'Audio energy - clap jumps BEFORE alignment', 'FontSize', S.title, 'FontName', S.font, 'FontWeight', 'bold');
        ylabel(axa1, 'energy', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
        lg1 = legend(axa1, leg, 'Location', 'northeast'); lg1.FontSize = S.legend; lg1.FontName = S.font;
        title(axa2, 'AFTER alignment - all claps line up', 'FontSize', S.title, 'FontName', S.font, 'FontWeight', 'bold');
        xlabel(axa2, 'time (s, real)', 'FontSize', S.xlbl, 'FontName', S.font, 'FontWeight', 'bold');
        ylabel(axa2, 'energy', 'FontSize', S.ylbl, 'FontName', S.font, 'FontWeight', 'bold');
        lg2 = legend(axa2, leg, 'Location', 'northeast'); lg2.FontSize = S.legend; lg2.FontName = S.font;
        for ax = [axa1 axa2]
            set(ax, 'FontName', S.font, 'FontSize', S.tick, 'FontWeight', 'bold', ...
                'LineWidth', S.boxLW, 'Box', 'on');
        end
        linkaxes([axa1 axa2], 'x');
    end

%% ======================= LOCAL FUNCTIONS =======================
function setstyle(H, mode, isObstacle, S)
    ks = keys(H);
    for i = 1:numel(ks)
        if isObstacle(ks{i}), continue; end   % obstacle stays scatter points
        h = H(ks{i});
        if mode == 1          % Line
            set(h, 'LineStyle', '-', 'Marker', 'none');
        else                  % Scatter
            set(h, 'LineStyle', 'none', 'Marker', '.', 'MarkerSize', S.footPt);
        end
    end
end

function c = markerColor(name, k, fallback)
% Colour each marker to MATCH its physical marker colour, so the plots read
% the same as the real setup. Unknown names fall back to the lines() colormap.
    switch lower(name)
        case 'l_toe',  c = [0.55 0.20 0.75];    % purple
        case 'l_heel', c = [0.15 0.65 0.20];    % green
        case 'r_toe',  c = [0.95 0.40 0.70];    % pink
        case 'r_heel', c = [0.10 0.60 0.60];    % teal
        otherwise
            if startsWith(lower(name), 'obstacle')   % red family (both are red balls)
                if endsWith(name, '2'), c = [0.60 0.08 0.08];   % darker red
                else,                   c = [0.90 0.15 0.15];   % red
                end
            else
                c = fallback(k, :);
            end
    end
end

function prep(ax)
    hold(ax, 'on'); grid(ax, 'on'); box(ax, 'on');
end

function s = onoff(v)
    if v, s = 'on'; else, s = 'off'; end
end
