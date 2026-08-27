function plot_audiosync(id)
% PLOT_AUDIOSYNC  Show the clap "jumps" in the audio used to time-sync the cameras.
%
%   plot_audiosync('test08')     % -> code/sessions/test08/test08_trajectory.xlsx
%   plot_audiosync('foo.xlsx')   % explicit file / full path
%
% Reads the "audio" sheet (written by build_multi_trajectory) with columns:
%   time_s, cam1_env, cam2_env, cam2_env_aligned
% Top axes:    the raw energy envelopes -- the two claps are the tall spikes,
%              sitting at DIFFERENT times (that gap is the camera time offset).
% Bottom axes: cam2 shifted by the offset -- the two claps now line up.

    if nargin < 1 || isempty(id)
        [f, p] = uigetfile({'*.xlsx', 'Trajectory files'}, 'Select a trajectory .xlsx');
        if isequal(f, 0), return; end
        datafile = fullfile(p, f);
    elseif exist(id, 'file')
        datafile = id;
    else
        root = fileparts(fileparts(mfilename('fullpath')));   % repo root
        datafile = fullfile(root, 'code', 'sessions', id, [id '_trajectory.xlsx']);
        if ~exist(datafile, 'file')
            error('No trajectory .xlsx for "%s". Looked for:\n  %s', id, datafile);
        end
    end
    if ~any(strcmp(sheetnames(datafile), 'audio'))
        error('No "audio" sheet in %s (re-run build_multi_trajectory to generate it).', datafile);
    end

    T = readtable(datafile, 'Sheet', 'audio');
    t = T.time_s;

    delete(findall(0, 'Type', 'figure', 'Tag', 'audiosyncfig'));
    fig = figure('Name', 'Audio clap sync', 'Color', 'w', ...
                 'Tag', 'audiosyncfig', 'Position', [200 200 900 560]);

    ax1 = subplot(2, 1, 1, 'Parent', fig); hold(ax1, 'on'); grid(ax1, 'on');
    plot(ax1, t, T.cam1_env, 'Color', [0.12 0.47 0.71], 'LineWidth', 1.0);
    plot(ax1, t, T.cam2_env, 'Color', [0.84 0.19 0.42], 'LineWidth', 1.0);
    title(ax1, 'Audio energy - clap jumps BEFORE alignment (the spikes are the claps)');
    ylabel(ax1, 'energy'); legend(ax1, {'cam1', 'cam2'}, 'Location', 'northeast');

    ax2 = subplot(2, 1, 2, 'Parent', fig); hold(ax2, 'on'); grid(ax2, 'on');
    plot(ax2, t, T.cam1_env, 'Color', [0.12 0.47 0.71], 'LineWidth', 1.0);
    plot(ax2, t, T.cam2_env_aligned, 'Color', [0.84 0.19 0.42], 'LineWidth', 1.0);
    title(ax2, 'AFTER alignment - the two claps line up');
    xlabel(ax2, 'time (s, real)'); ylabel(ax2, 'energy');
    legend(ax2, {'cam1', 'cam2 (shifted)'}, 'Location', 'northeast');
    linkaxes([ax1 ax2], 'x');
end
