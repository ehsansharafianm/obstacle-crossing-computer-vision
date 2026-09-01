function outputs = process_session_results(testNumber, varargin)
% PROCESS_SESSION_RESULTS  Plot and animate one obstacle-crossing session.
%
%   process_session_results('test11')
%   process_session_results('test11', 'MakeVideo', false)
%   process_session_results('test11', 'StartTime', 10, 'EndTime', 20)
%   process_session_results('test11', 'TrailSeconds', 5, 'PlaybackSpeed', 1)
%
% Reads results/sessions/testNN/testNN_trajectory.xlsx. The marker sheet must use
% columns named time_s and <marker>_x_mm/<marker>_y_mm/<marker>_z_mm. Marker
% names are discovered automatically, so future marker sets also work.
%
% Outputs are written to results/sessions/testNN/processed-outputs/:
%   testNN_postprocess_3d.png
%   testNN_postprocess_xyz_time.png
%   testNN_marker_animation.mp4       (unless MakeVideo is false)
%
% Timing convention:
%   trajectory time 0 s = clap
%   synced video time 2 s = clap
% Therefore: synced-video time = trajectory time + 2.000 s.

    p = inputParser;
    addRequired(p, 'testNumber', @(x) ischar(x) || isstring(x));
    addParameter(p, 'MakeVideo', true, @(x) islogical(x) && isscalar(x));
    addParameter(p, 'StartTime', -inf, @(x) isnumeric(x) && isscalar(x));
    addParameter(p, 'EndTime', inf, @(x) isnumeric(x) && isscalar(x));
    addParameter(p, 'TrailSeconds', 5, @(x) isnumeric(x) && isscalar(x) && x > 0);
    addParameter(p, 'PlaybackSpeed', 1, @(x) isnumeric(x) && isscalar(x) && x > 0);
    addParameter(p, 'OutputFrameRate', 10, @(x) isnumeric(x) && isscalar(x) && x > 0);
    addParameter(p, 'VideoQuality', 90, @(x) isnumeric(x) && isscalar(x) && x >= 0 && x <= 100);
    addParameter(p, 'Visible', false, @(x) islogical(x) && isscalar(x));
    addParameter(p, 'MakeStaticPlots', true, @(x) islogical(x) && isscalar(x));
    addParameter(p, 'VideoFilename', '', @(x) ischar(x) || isstring(x));
    parse(p, testNumber, varargin{:});
    opt = p.Results;

    testId = normalize_test_id(testNumber);
    repoRoot = fileparts(fileparts(mfilename('fullpath')));
    sessionDir = fullfile(repoRoot, 'results', 'sessions', testId);
    outputDir = fullfile(sessionDir, 'processed-outputs');
    if ~isfolder(outputDir), mkdir(outputDir); end
    datafile = fullfile(sessionDir, [testId '_trajectory.xlsx']);
    if ~isfile(datafile)
        error('Trajectory workbook not found: %s', datafile);
    end

    T = readtable(datafile, 'Sheet', 'markers');
    if ~ismember('time_s', T.Properties.VariableNames)
        error('The markers sheet must contain a time_s column.');
    end
    t = double(T.time_s(:));
    goodTime = isfinite(t);
    T = T(goodTime, :);
    t = t(goodTime);
    [t, order] = sort(t);
    T = T(order, :);
    if numel(t) < 2
        error('At least two valid trajectory samples are required.');
    end

    [names, xyz, isObstacle] = read_markers(T, datafile, t);
    colors = marker_colors(names);

    startTime = max(t(1), opt.StartTime);
    endTime = min(t(end), opt.EndTime);
    if startTime > endTime
        error('Requested time range does not overlap the workbook (%.3f to %.3f s).', t(1), t(end));
    end

    outputs = struct();
    outputs.datafile = datafile;
    outputs.outputDirectory = outputDir;
    outputs.figure3d = fullfile(outputDir, [testId '_postprocess_3d.png']);
    outputs.figureTime = fullfile(outputDir, [testId '_postprocess_xyz_time.png']);
    videoFilename = char(string(opt.VideoFilename));
    if isempty(videoFilename)
        videoFilename = [testId '_marker_animation.mp4'];
    end
    [videoFolder, videoStem, videoExt] = fileparts(videoFilename);
    if ~isempty(videoFolder)
        error('VideoFilename must be a filename only; output is always saved in the session folder.');
    end
    if isempty(videoExt), videoExt = '.mp4'; end
    if ~strcmpi(videoExt, '.mp4'), error('VideoFilename must use the .mp4 extension.'); end
    outputs.video = fullfile(outputDir, [videoStem videoExt]);
    outputs.trajectoryTimeRange_s = [t(1), t(end)];
    outputs.syncedVideoOffset_s = 2.0;

    visibility = ternary(opt.Visible, 'on', 'off');
    if opt.MakeStaticPlots
        make_static_3d(t, names, xyz, isObstacle, colors, testId, outputs.figure3d, visibility);
        make_static_time(t, names, xyz, isObstacle, colors, testId, outputs.figureTime, visibility);
    else
        outputs.figure3d = '';
        outputs.figureTime = '';
    end

    dt = diff(t);
    sampleRate = 1 / median(dt(isfinite(dt) & dt > 0));
    outputs.estimatedSampleRate_Hz = sampleRate;
    fprintf('[%s] %d samples, %.3f to %.3f s, estimated %.3f Hz\n', ...
        testId, numel(t), t(1), t(end), sampleRate);
    if opt.MakeStaticPlots
        fprintf('Saved: %s\nSaved: %s\n', outputs.figure3d, outputs.figureTime);
    end

    if opt.MakeVideo
        make_animation(t, names, xyz, isObstacle, colors, testId, outputs.video, ...
            startTime, endTime, opt.TrailSeconds, opt.PlaybackSpeed, ...
            opt.OutputFrameRate, opt.VideoQuality, visibility);
        fprintf('Saved: %s\n', outputs.video);
        fprintf('Sync rule: animation trajectory t + 2.000 s = synced-video time.\n');
    else
        outputs.video = '';
    end
end

function testId = normalize_test_id(value)
    s = char(string(value));
    token = regexp(strtrim(lower(s)), '^test(\d+)$', 'tokens', 'once');
    if isempty(token)
        error('Input must be a session name such as ''test11''.');
    end
    testId = sprintf('test%02d', str2double(token{1}));
end

function [names, xyz, isObstacle] = read_markers(T, datafile, t)
    vars = T.Properties.VariableNames;
    names = {};
    xyz = {};
    for k = 1:numel(vars)
        token = regexp(vars{k}, '^(.*)_x_mm$', 'tokens', 'once');
        if isempty(token), continue; end
        name = token{1};
        required = {[name '_x_mm'], [name '_y_mm'], [name '_z_mm']};
        if all(ismember(required, vars))
            names{end+1} = name; %#ok<AGROW>
            xyz{end+1} = double(T{:, required}); %#ok<AGROW>
        end
    end
    if isempty(names)
        error('No complete <marker>_x_mm/y_mm/z_mm column sets were found.');
    end

    % Older workbooks (including test11) store the two obstacle points on a
    % separate sheet. Promote them to time-series markers for common plotting.
    sheets = sheetnames(datafile);
    obstacleSheet = '';
    if any(strcmpi(sheets, 'obstacle')), obstacleSheet = 'obstacle';
    elseif any(strcmpi(sheets, 'ground')), obstacleSheet = 'ground';
    end
    alreadyHasObstacle = any(startsWith(lower(string(names)), 'obstacle'));
    if ~isempty(obstacleSheet) && ~alreadyHasObstacle
        G = readtable(datafile, 'Sheet', obstacleSheet);
        gv = G.Properties.VariableNames;
        if all(ismember({'x_mm', 'y_mm', 'z_mm'}, gv))
            for j = 1:height(G)
                names{end+1} = sprintf('obstacle%d', j); %#ok<AGROW>
                point = double(G{j, {'x_mm', 'y_mm', 'z_mm'}});
                xyz{end+1} = repmat(point, numel(t), 1); %#ok<AGROW>
            end
        end
    end
    isObstacle = startsWith(lower(string(names)), 'obstacle');
end

function colors = marker_colors(names)
    preferred = containers.Map( ...
        {'L_toe','L_heel','R_toe','R_heel','obstacle1','obstacle2'}, ...
        {[0.49 0.23 0.93],[0.13 0.65 0.35],[0.84 0.20 0.42], ...
         [0.06 0.60 0.68],[0.10 0.10 0.10],[0.55 0.55 0.55]});
    fallback = lines(max(7, numel(names)));
    colors = zeros(numel(names), 3);
    for k = 1:numel(names)
        if isKey(preferred, names{k}), colors(k, :) = preferred(names{k});
        else, colors(k, :) = fallback(k, :);
        end
    end
end

function make_static_3d(~, names, xyz, isObstacle, colors, testId, outfile, visibility)
    f = figure('Color', 'w', 'Visible', visibility, 'Position', [100 100 1100 800]);
    cleaner = onCleanup(@() close(f));
    ax = axes(f); hold(ax, 'on'); grid(ax, 'on'); box(ax, 'on');
    for k = 1:numel(names)
        d = xyz{k};
        if isObstacle(k)
            scatter3(ax, d(:,1), d(:,2), d(:,3), 45, colors(k,:), 'filled', ...
                'DisplayName', names{k});
        else
            plot3(ax, d(:,1), d(:,2), d(:,3), '-', 'Color', colors(k,:), ...
                'LineWidth', 1.8, 'DisplayName', names{k});
        end
    end
    xlabel(ax, 'X (mm)'); ylabel(ax, 'Y (mm)'); zlabel(ax, 'Z (mm)');
    title(ax, sprintf('%s marker trajectories', testId), 'Interpreter', 'none');
    legend(ax, 'Location', 'best', 'Interpreter', 'none');
    view(ax, 3); axis(ax, 'equal'); style_axes(ax);
    exportgraphics(f, outfile, 'Resolution', 180);
end

function make_static_time(t, names, xyz, isObstacle, colors, testId, outfile, visibility)
    f = figure('Color', 'w', 'Visible', visibility, 'Position', [100 100 1300 900]);
    cleaner = onCleanup(@() close(f));
    tl = tiledlayout(f, 3, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
    labels = {'X (mm)', 'Y (mm)', 'Z (mm)'};
    for a = 1:3
        ax = nexttile(tl); hold(ax, 'on'); grid(ax, 'on'); box(ax, 'on');
        for k = 1:numel(names)
            if isObstacle(k), lineStyle = '--'; else, lineStyle = '-'; end
            plot(ax, t, xyz{k}(:,a), lineStyle, 'Color', colors(k,:), ...
                'LineWidth', 1.25, 'DisplayName', names{k});
        end
        ylabel(ax, labels{a}); style_axes(ax);
        if a < 3, ax.XTickLabel = {}; else, xlabel(ax, 'Trajectory time from clap (s)'); end
        if a == 1
            title(ax, sprintf('%s marker positions versus time', testId), 'Interpreter', 'none');
            legend(ax, 'Location', 'eastoutside', 'Interpreter', 'none');
        end
    end
    linkaxes(findall(f, 'Type', 'axes'), 'x');
    exportgraphics(f, outfile, 'Resolution', 180);
end

function make_animation(t, names, xyz, isObstacle, colors, testId, outfile, ...
        startTime, endTime, trailSeconds, playbackSpeed, outputFps, quality, visibility)
    % Obstacles are useful in the static plots, but intentionally omitted from
    % the animation. The moving display contains foot markers only.
    keep = ~isObstacle;
    names = names(keep);
    xyz = xyz(keep);
    colors = colors(keep, :);
    if isempty(names), error('No non-obstacle markers are available to animate.'); end

    frameTimes = startTime:(playbackSpeed/outputFps):endTime;
    if frameTimes(end) < endTime, frameTimes(end+1) = endTime; end

    % The figure may remain hidden for unattended/background video rendering.
    f = figure('Color', 'w', 'Visible', visibility, 'Position', [40 40 1600 900], ...
        'Name', [testId ' marker animation']);
    cleaner = onCleanup(@() close(f));
    tl = tiledlayout(f, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
    ax3 = nexttile(tl, 1, [2 1]); hold(ax3, 'on'); grid(ax3, 'on'); box(ax3, 'on');
    axHeightDistance = nexttile(tl, 2);
    axHeightTime = nexttile(tl, 4);
    hold(axHeightDistance, 'on'); grid(axHeightDistance, 'on'); box(axHeightDistance, 'on');
    hold(axHeightTime, 'on'); grid(axHeightTime, 'on'); box(axHeightTime, 'on');

    allData = vertcat(xyz{:});
    lim = padded_limits(allData);
    xlim(ax3, lim(1,:)); ylim(ax3, lim(2,:)); zlim(ax3, lim(3,:));
    xlabel(ax3, 'X (mm)'); ylabel(ax3, 'Y (mm)'); zlabel(ax3, 'Z (mm)');
    view(ax3, 3); axis(ax3, 'vis3d'); style_axes(ax3);

    xyDistance = cellfun(@(d) hypot(d(:,1), d(:,2)), xyz, 'UniformOutput', false);
    allDistance = vertcat(xyDistance{:});
    allZ = cellfun(@(d) d(:,3), xyz, 'UniformOutput', false);
    allZ = vertcat(allZ{:});
    xlim(axHeightDistance, padded_limits(allDistance));
    ylim(axHeightDistance, padded_limits(allZ));
    xlabel(axHeightDistance, 'Horizontal XY distance, sqrt(X^2 + Y^2) (mm)');
    ylabel(axHeightDistance, 'Z height (mm)');
    title(axHeightDistance, 'Height versus horizontal distance');
    style_axes(axHeightDistance);

    xlim(axHeightTime, [startTime endTime]);
    ylim(axHeightTime, padded_limits(allZ));
    xlabel(axHeightTime, 'Trajectory time from clap (s)');
    ylabel(axHeightTime, 'Z height (mm)');
    title(axHeightTime, 'Height versus time');
    style_axes(axHeightTime);

    history3 = gobjects(numel(names),1); current3 = gobjects(numel(names),1);
    historyHeightDistance = gobjects(numel(names),1);
    currentHeightDistance = gobjects(numel(names),1);
    historyHeightTime = gobjects(numel(names),1);
    currentHeightTime = gobjects(numel(names),1);
    for k = 1:numel(names)
        history3(k) = plot3(ax3, nan, nan, nan, '-', 'Color', colors(k,:), ...
            'LineWidth', 1.6, 'DisplayName', names{k});
        current3(k) = plot3(ax3, nan, nan, nan, 'o', 'Color', colors(k,:), ...
            'MarkerFaceColor', colors(k,:), 'MarkerSize', 7, ...
            'HandleVisibility', 'off');
        historyHeightDistance(k) = plot(axHeightDistance, nan, nan, '-', ...
            'Color', colors(k,:), 'LineWidth', 1.2);
        currentHeightDistance(k) = plot(axHeightDistance, nan, nan, 'o', ...
            'Color', colors(k,:), 'MarkerFaceColor', colors(k,:), 'MarkerSize', 5);
        historyHeightTime(k) = plot(axHeightTime, nan, nan, '-', ...
            'Color', colors(k,:), 'LineWidth', 1.2);
        currentHeightTime(k) = plot(axHeightTime, nan, nan, 'o', ...
            'Color', colors(k,:), 'MarkerFaceColor', colors(k,:), 'MarkerSize', 5);
    end
    legend(ax3, 'Location', 'best', 'Interpreter', 'none');
    cursor = xline(axHeightTime, startTime, 'k-', 'LineWidth', 1.2);
    titleHandle = title(ax3, '');

    writer = VideoWriter(outfile, 'MPEG-4');
    writer.FrameRate = outputFps;
    writer.Quality = quality;
    open(writer);
    writerCleaner = onCleanup(@() close(writer));

    reportEvery = max(1, round(numel(frameTimes)/20));
    for frameIndex = 1:numel(frameTimes)
        q = frameTimes(frameIndex);
        % Rolling trail: retain only [current time - TrailSeconds, current time].
        % Data older than this window disappears from all three panels.
        trailStart = q - trailSeconds;
        use = t >= trailStart & t <= q;
        [~, currentIndex] = min(abs(t - q));
        for k = 1:numel(names)
            d = xyz{k};
            distance = xyDistance{k};
            set(history3(k), 'XData', d(use,1), 'YData', d(use,2), 'ZData', d(use,3));
            set(historyHeightDistance(k), 'XData', distance(use), 'YData', d(use,3));
            set(historyHeightTime(k), 'XData', t(use), 'YData', d(use,3));
            now = d(currentIndex,:);
            if all(isfinite(now))
                set(current3(k), 'XData', now(1), 'YData', now(2), 'ZData', now(3));
            else
                set(current3(k), 'XData', nan, 'YData', nan, 'ZData', nan);
            end
            if all(isfinite(now))
                set(currentHeightDistance(k), 'XData', hypot(now(1), now(2)), 'YData', now(3));
            else
                set(currentHeightDistance(k), 'XData', nan, 'YData', nan);
            end
            if isfinite(now(3))
                set(currentHeightTime(k), 'XData', q, 'YData', now(3));
            else
                set(currentHeightTime(k), 'XData', nan, 'YData', nan);
            end
        end
        set(cursor, 'Value', q);
        set(titleHandle, 'String', sprintf('%s | trajectory: %7.3f s | synced video: %7.3f s', ...
            testId, q, q + 2.0), 'Interpreter', 'none');
        drawnow limitrate nocallbacks;
        writeVideo(writer, getframe(f));
        if mod(frameIndex, reportEvery) == 0 || frameIndex == numel(frameTimes)
            fprintf('Animation: %5.1f%% (%d/%d frames)\n', ...
                100*frameIndex/numel(frameTimes), frameIndex, numel(frameTimes));
        end
    end
end

function lim = padded_limits(data)
    if isvector(data), data = data(:); end
    lim = zeros(size(data,2), 2);
    for k = 1:size(data,2)
        v = data(:,k); v = v(isfinite(v));
        if isempty(v), lo = -1; hi = 1; else, lo = min(v); hi = max(v); end
        span = hi - lo;
        if span <= 0, span = max(abs(lo)*0.1, 1); end
        pad = 0.06 * span;
        lim(k,:) = [lo-pad, hi+pad];
    end
    if size(lim,1) == 1, lim = lim(1,:); end
end

function style_axes(ax)
    set(ax, 'FontName', 'Arial', 'FontSize', 12, 'LineWidth', 1.1, 'Box', 'on');
end

function out = ternary(condition, a, b)
    if condition, out = a; else, out = b; end
end
