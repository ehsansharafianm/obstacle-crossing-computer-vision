function plot_trajectory(csvfile)
% PLOT_TRAJECTORY  Interactive 3D + X/Y/Z-vs-time plot of marker trajectories.
%
%   plot_trajectory                 % opens a file picker
%   plot_trajectory('foot_trajectory.csv')
%
% Expects a CSV exported by the obstacle-crossing pipeline, with columns:
%   time_s, <marker>_x_mm, <marker>_y_mm, <marker>_z_mm, ...
% Any number of markers is supported (names auto-detected from the headers),
% so this same function works for the foot pilot, the wand, or a full 6-marker
% shoe in future recordings.
%
% Left panel  : 3D trajectory of every marker.
% Right panel : X, Y, Z position vs time (three stacked axes).
% Checkboxes (top-left) toggle each marker ON/OFF in BOTH panels at once.

    if nargin < 1 || isempty(csvfile)
        [f, p] = uigetfile('*.csv', 'Select a trajectory CSV');
        if isequal(f, 0), return; end
        csvfile = fullfile(p, f);
    end

    T  = readtable(csvfile);
    vn = T.Properties.VariableNames;
    if ~ismember('time_s', vn)
        error('CSV must have a "time_s" column.');
    end
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

    % --- figure & layout ---
    fig = figure('Name', 'Marker trajectories', 'Color', 'w', ...
                 'Position', [80 80 1360 680]);

    ax3 = axes('Parent', fig, 'Position', [0.05 0.10 0.44 0.80]);
    hold(ax3, 'on'); grid(ax3, 'on'); box(ax3, 'on');
    xlabel(ax3, 'X (mm)'); ylabel(ax3, 'Y (mm)'); zlabel(ax3, 'Z (mm)');
    title(ax3, '3D trajectory'); view(ax3, 3); axis(ax3, 'equal'); rotate3d(ax3, 'on');

    axX = axes('Parent', fig, 'Position', [0.58 0.68 0.38 0.24]); prep(axX); ylabel(axX, 'X (mm)');
    title(axX, 'Position vs time');
    axY = axes('Parent', fig, 'Position', [0.58 0.40 0.38 0.24]); prep(axY); ylabel(axY, 'Y (mm)');
    axZ = axes('Parent', fig, 'Position', [0.58 0.10 0.38 0.24]); prep(axZ); ylabel(axZ, 'Z (mm)');
    xlabel(axZ, 'time (s)');
    linkaxes([axX axY axZ], 'x');

    % --- plot each marker, storing its graphics handles ---
    H = containers.Map();
    for k = 1:nM
        m = markers{k}; c = cmap(k, :);
        x = T.([m '_x_mm']); y = T.([m '_y_mm']); z = T.([m '_z_mm']);
        h = gobjects(1, 4);
        h(1) = plot3(ax3, x, y, z, '.-', 'Color', c, 'MarkerSize', 7, ...
                     'LineWidth', 1.0, 'DisplayName', m);
        h(2) = plot(axX, t, x, '-', 'Color', c, 'LineWidth', 1.2);
        h(3) = plot(axY, t, y, '-', 'Color', c, 'LineWidth', 1.2);
        h(4) = plot(axZ, t, z, '-', 'Color', c, 'LineWidth', 1.2);
        H(m) = h;
    end
    legend(ax3, 'show', 'Location', 'best', 'Interpreter', 'none');

    % --- one checkbox per marker (toggles both panels) ---
    for k = 1:nM
        m = markers{k};
        uicontrol(fig, 'Style', 'checkbox', 'String', m, 'Value', 1, ...
            'Units', 'normalized', 'Position', [0.05 0.955-0.032*(k-1) 0.16 0.03], ...
            'BackgroundColor', 'w', 'FontWeight', 'bold', ...
            'ForegroundColor', cmap(k, :), ...
            'Callback', @(src, ~) set(H(m), 'Visible', onoff(src.Value)));
    end
end

function prep(ax)
    hold(ax, 'on'); grid(ax, 'on'); box(ax, 'on');
end

function s = onoff(v)
    if v, s = 'on'; else, s = 'off'; end
end
