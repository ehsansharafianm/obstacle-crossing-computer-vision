function plot_trajectory(csvfile)
% PLOT_TRAJECTORY  Interactive 3D + X/Y/Z-vs-time plot of marker trajectories.
%
%   plot_trajectory                 % opens a file picker
%   plot_trajectory('test01')       % -> code/experiments/test01/test01_trajectory.csv
%   plot_trajectory('foot_trajectory.csv')      % explicit file / full path
%
% CSV columns (exported by the obstacle-crossing pipeline):
%   time_s, <marker>_x_mm, <marker>_y_mm, <marker>_z_mm, ...
% Any number of markers is supported (names auto-detected from the headers).
%
% Left panel  : 3D trajectory.   Right panel : X, Y, Z vs time (stacked).
% Controls (top-left):
%   * one checkbox per marker  -> toggle it ON/OFF in BOTH panels
%   * Line / Scatter dropdown  -> switch every marker between a connected line
%                                 and points only.

    if nargin < 1 || isempty(csvfile)
        [f, p] = uigetfile('*.csv', 'Select a trajectory CSV');
        if isequal(f, 0), return; end
        csvfile = fullfile(p, f);
    elseif ~exist(csvfile, 'file') && ~endsWith(lower(csvfile), '.csv')
        % A bare test id (e.g. 'test01') -> code/experiments/<id>/<id>_trajectory.csv,
        % resolved relative to this .m file so it works from any MATLAB cwd.
        id   = csvfile;
        root = fileparts(fileparts(mfilename('fullpath')));   % repo root
        cand = fullfile(root, 'code', 'experiments', id, [id '_trajectory.csv']);
        if exist(cand, 'file')
            csvfile = cand;
        else
            error('No CSV for test "%s". Looked for:\n  %s', id, cand);
        end
    end

    % --- close any previous window opened by this function ---
    delete(findall(0, 'Type', 'figure', 'Tag', 'trajfig'));

    T  = readtable(csvfile);
    vn = T.Properties.VariableNames;
    if ~ismember('time_s', vn), error('CSV must have a "time_s" column.'); end
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

    % --- figure & axes ---
    fig = figure('Name', 'Marker trajectories', 'Color', 'w', ...
                 'Tag', 'trajfig', 'Position', [80 80 1360 680]);

    ax3 = axes('Parent', fig, 'Position', [0.05 0.10 0.44 0.80]);
    hold(ax3, 'on'); grid(ax3, 'on'); box(ax3, 'on');
    xlabel(ax3, 'X (mm)'); ylabel(ax3, 'Y (mm)'); zlabel(ax3, 'Z (mm)');
    title(ax3, '3D trajectory'); view(ax3, 3); axis(ax3, 'equal'); rotate3d(ax3, 'on');

    axX = axes('Parent', fig, 'Position', [0.58 0.68 0.38 0.24]); prep(axX); ylabel(axX, 'X (mm)');
    title(axX, 'Position vs time');
    axY = axes('Parent', fig, 'Position', [0.58 0.40 0.38 0.24]); prep(axY); ylabel(axY, 'Y (mm)');
    axZ = axes('Parent', fig, 'Position', [0.58 0.10 0.38 0.24]); prep(axZ); ylabel(axZ, 'Z (mm)');
    xlabel(axZ, 'time (s)');

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
    legend(ax3, 'show', 'Location', 'best', 'Interpreter', 'none');

    % --- set time axes to the data range, THEN link (order matters) ---
    tv = t(any(~isnan(T{:, 2:end}), 2));           % times with any marker data
    if ~isempty(tv), xlim(axX, [min(tv) max(tv)]); end
    arrayfun(@(a) axis(a, 'auto y'), [axX axY axZ]);
    linkaxes([axX axY axZ], 'x');

    % --- per-marker on/off checkboxes ---
    for k = 1:nM
        m = markers{k};
        uicontrol(fig, 'Style', 'checkbox', 'String', m, 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.030*(k-1) 0.16 0.028], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', 'ForegroundColor', cmap(k, :), ...
            'Callback', @(src, ~) set(H(m), 'Visible', onoff(src.Value)));
    end

    % --- Line / Scatter style dropdown ---
    uicontrol(fig, 'Style', 'text', 'String', 'style:', 'Units', 'normalized', ...
        'Position', [0.05 0.955-0.030*nM-0.03 0.05 0.026], 'BackgroundColor', 'w', ...
        'HorizontalAlignment', 'left');
    uicontrol(fig, 'Style', 'popupmenu', 'String', {'Line', 'Scatter'}, ...
        'Units', 'normalized', 'Position', [0.10 0.955-0.030*nM-0.03 0.11 0.028], ...
        'Callback', @(src, ~) setstyle(H, src.Value));
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
