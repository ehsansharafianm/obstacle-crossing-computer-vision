function plot_trajectory(csvfile)
% PLOT_TRAJECTORY  Interactive 3D + X/Y/Z-vs-time plot of marker trajectories.
%
%   plot_trajectory                 % opens a file picker
%   plot_trajectory('test07')       % -> code/sessions/test07/test07_trajectory.xlsx
%   plot_trajectory('foot_trajectory.csv')      % explicit file / full path
%
% Reads the marker trajectories (a .xlsx "markers" sheet, or a plain .csv):
%   time_s, <marker>_x_mm, <marker>_y_mm, <marker>_z_mm, ...
% Any number of markers is supported (names auto-detected from the headers).
% If the .xlsx also has a "ground" sheet, those static points are drawn in 3D.
%
% Opens up to THREE figures: (1) the 3D trajectory, (2) X / Y / Z vs time, and
% (3) the audio clap-sync (if the .xlsx has an 'audio' sheet) showing the clap
% jumps before/after alignment. Re-running closes the previous set first.
% Controls (on the 3D figure, top-left):
%   * one checkbox per marker  -> toggle it ON/OFF in BOTH panels
%   * Line / Scatter dropdown  -> switch every marker between a connected line
%                                 and points only.

    if nargin < 1 || isempty(csvfile)
        [f, p] = uigetfile({'*.xlsx;*.csv', 'Trajectory files'}, 'Select a trajectory file');
        if isequal(f, 0), return; end
        datafile = fullfile(p, f);
    elseif exist(csvfile, 'file')
        datafile = csvfile;                                   % explicit path given
    else
        % A bare test id (e.g. 'test07') -> code/sessions/<id>/<id>_trajectory.xlsx
        % (falls back to .csv), resolved relative to this .m file.
        id   = csvfile;
        root = fileparts(fileparts(mfilename('fullpath')));   % repo root
        candx = fullfile(root, 'code', 'sessions', id, [id '_trajectory.xlsx']);
        candc = fullfile(root, 'code', 'sessions', id, [id '_trajectory.csv']);
        if exist(candx, 'file'),     datafile = candx;
        elseif exist(candc, 'file'), datafile = candc;
        else,  error('No trajectory file for "%s". Looked for:\n  %s\n  %s', id, candx, candc);
        end
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
    cmap = lines(max(nM, 3));

    % --- TWO separate figures (both tagged 'trajfig' so a re-run closes both) ---
    % Figure 1: the 3D trajectory (carries the marker/ground toggles).
    fig3 = figure('Name', 'Marker trajectories - 3D', 'Color', 'w', ...
                  'Tag', 'trajfig', 'Position', [70 130 740 700]);
    ax3 = axes('Parent', fig3, 'Position', [0.13 0.09 0.82 0.84]);
    hold(ax3, 'on'); grid(ax3, 'on'); box(ax3, 'on');
    xlabel(ax3, 'X (mm)'); ylabel(ax3, 'Y (mm)'); zlabel(ax3, 'Z (mm)');
    title(ax3, '3D trajectory'); view(ax3, 3); axis(ax3, 'equal'); rotate3d(ax3, 'on');

    % Figure 2: X / Y / Z vs time.
    figp = figure('Name', 'Marker positions vs time', 'Color', 'w', ...
                  'Tag', 'trajfig', 'Position', [830 130 640 700]);
    axX = axes('Parent', figp, 'Position', [0.12 0.70 0.83 0.25]); prep(axX); ylabel(axX, 'X (mm)');
    title(axX, 'Position vs time');
    axY = axes('Parent', figp, 'Position', [0.12 0.40 0.83 0.25]); prep(axY); ylabel(axY, 'Y (mm)');
    axZ = axes('Parent', figp, 'Position', [0.12 0.09 0.83 0.25]); prep(axZ);
    xlabel(axZ, 'time (s)'); ylabel(axZ, 'Z (mm)');

    % --- plot each marker, storing its graphics handles ---
    H = containers.Map();
    for k = 1:nM
        m = markers{k}; c = cmap(k, :);
        x = T.([m '_x_mm']); y = T.([m '_y_mm']); z = T.([m '_z_mm']);
        h = gobjects(1, 4);
        h(1) = plot3(ax3, x, y, z, '-', 'Color', c, 'Marker', 'none', ...
                     'MarkerSize', 7, 'LineWidth', 1.2, 'DisplayName', m);
        h(2) = plot(axX, t, x, '-', 'Color', c, 'Marker', 'none', 'LineWidth', 1.2);
        h(3) = plot(axY, t, y, '-', 'Color', c, 'Marker', 'none', 'LineWidth', 1.2);
        h(4) = plot(axZ, t, z, '-', 'Color', c, 'Marker', 'none', 'LineWidth', 1.2);
        H(m) = h;
    end

    % --- overlay the static ground markers (from the 'ground' sheet), if any ---
    gh = gobjects(0);                       % handle(s) for the ground toggle
    if isxlsx
        try
            sh = sheetnames(datafile);
            if any(strcmp(sh, 'ground'))
                G = readtable(datafile, 'Sheet', 'ground');
                gh = plot3(ax3, G.x_mm, G.y_mm, G.z_mm, 's-', 'Color', [0.85 0.12 0.12], ...
                      'LineWidth', 1.6, 'MarkerSize', 12, 'MarkerFaceColor', [0.85 0.12 0.12], ...
                      'MarkerEdgeColor', 'k', 'DisplayName', 'ground');
            end
        catch
        end
    end
    legend(ax3, 'show', 'Location', 'best', 'Interpreter', 'none');

    % --- set time axes to the data range, THEN link (order matters) ---
    tv = t(any(~isnan(T{:, 2:end}), 2));           % times with any marker data
    if ~isempty(tv), xlim(axX, [min(tv) max(tv)]); end
    arrayfun(@(a) axis(a, 'auto y'), [axX axY axZ]);
    linkaxes([axX axY axZ], 'x');

    % --- per-marker on/off checkboxes ---
    for k = 1:nM
        m = markers{k};
        uicontrol(fig3, 'Style', 'checkbox', 'String', m, 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.030*(k-1) 0.16 0.028], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', cmap(k, :), ...
            'Callback', @(src, ~) set(H(m), 'Visible', onoff(src.Value)));
    end

    % --- ground on/off checkbox (static markers, drawn as squares joined by a line) ---
    nRows = nM;
    if ~isempty(gh)
        uicontrol(fig3, 'Style', 'checkbox', 'String', 'ground', 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.030*nM 0.16 0.028], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', [0.85 0.12 0.12], ...
            'Callback', @(src, ~) set(gh, 'Visible', onoff(src.Value)));
        nRows = nM + 1;
    end

    % --- Line / Scatter style dropdown ---
    uicontrol(fig3, 'Style', 'text', 'String', 'style:', 'Units', 'normalized', ...
        'Position', [0.05 0.955-0.030*nRows-0.03 0.05 0.026], 'BackgroundColor', 'w', ...
        'HorizontalAlignment', 'left');
    uicontrol(fig3, 'Style', 'popupmenu', 'String', {'Line', 'Scatter'}, ...
        'Units', 'normalized', 'Position', [0.10 0.955-0.030*nRows-0.03 0.11 0.028], ...
        'Callback', @(src, ~) setstyle(H, src.Value));

    % --- Figure 3: the audio clap sync (only if the .xlsx has an 'audio' sheet) --
    if isxlsx && any(strcmp(sheetnames(datafile), 'audio'))
        A = readtable(datafile, 'Sheet', 'audio'); ta = A.time_s;
        figa = figure('Name', 'Audio clap sync', 'Color', 'w', ...
                      'Tag', 'trajfig', 'Position', [200 90 900 520]);
        axa1 = subplot(2, 1, 1, 'Parent', figa); hold(axa1, 'on'); grid(axa1, 'on');
        plot(axa1, ta, A.cam1_env, 'Color', [0.12 0.47 0.71], 'LineWidth', 1.0);
        plot(axa1, ta, A.cam2_env, 'Color', [0.84 0.19 0.42], 'LineWidth', 1.0);
        title(axa1, 'Audio energy - clap jumps BEFORE alignment (the spikes are the claps)');
        ylabel(axa1, 'energy'); legend(axa1, {'cam1', 'cam2'}, 'Location', 'northeast');
        axa2 = subplot(2, 1, 2, 'Parent', figa); hold(axa2, 'on'); grid(axa2, 'on');
        plot(axa2, ta, A.cam1_env, 'Color', [0.12 0.47 0.71], 'LineWidth', 1.0);
        plot(axa2, ta, A.cam2_env_aligned, 'Color', [0.84 0.19 0.42], 'LineWidth', 1.0);
        title(axa2, 'AFTER alignment - the two claps line up');
        xlabel(axa2, 'time (s, real)'); ylabel(axa2, 'energy');
        legend(axa2, {'cam1', 'cam2 (shifted)'}, 'Location', 'northeast');
        linkaxes([axa1 axa2], 'x');
    end
end

function setstyle(H, mode)
    ks = keys(H);
    for i = 1:numel(ks)
        h = H(ks{i});
        if mode == 1          % Line
            set(h, 'LineStyle', '-', 'Marker', 'none');
        else                  % Scatter
            set(h, 'LineStyle', 'none', 'Marker', '.', 'MarkerSize', 8);
        end
    end
end

function prep(ax)
    hold(ax, 'on'); grid(ax, 'on'); box(ax, 'on');
end

function s = onoff(v)
    if v, s = 'on'; else, s = 'off'; end
end
