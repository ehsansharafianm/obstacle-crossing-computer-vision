function output = make_session_video(testNumber)
% MAKE_SESSION_VIDEO  Interactively choose a time window and playback speed.
%
%   make_session_video('test11')
%
% A dialog shows the available trajectory-time range. Enter the beginning,
% ending, and playback speed. The resulting 60 fps MP4 is saved in the selected
% session folder with the time range and speed encoded in its filename.
%
% Time relationship to the synchronized camera clips:
%   synced-video time = trajectory time + 2.000 seconds.

    if nargin < 1 || isempty(testNumber)
        answer = inputdlg({'Test number:'}, 'Choose session', [1 35], {'11'});
        if isempty(answer), output = []; return; end
        testNumber = answer{1};
    end

    testId = normalize_test_id(testNumber);
    repoRoot = fileparts(fileparts(mfilename('fullpath')));
    workbook = fullfile(repoRoot, 'results', 'sessions', testId, [testId '_trajectory.xlsx']);
    if ~isfile(workbook), error('Trajectory workbook not found: %s', workbook); end

    T = readtable(workbook, 'Sheet', 'markers');
    if ~ismember('time_s', T.Properties.VariableNames)
        error('The markers sheet must contain a time_s column.');
    end
    t = double(T.time_s(:));
    t = t(isfinite(t));
    if isempty(t), error('No valid trajectory times were found.'); end
    availableStart = min(t);
    availableEnd = max(t);
    positiveDt = diff(sort(t));
    positiveDt = positiveDt(isfinite(positiveDt) & positiveDt > 0);
    if isempty(positiveDt), sampleTolerance = 1e-3;
    else, sampleTolerance = max(median(positiveDt), 1e-3);
    end

    prompts = { ...
        sprintf('Beginning trajectory time (available %.3f to %.3f s):', availableStart, availableEnd), ...
        sprintf('Ending trajectory time (available %.3f to %.3f s):', availableStart, availableEnd), ...
        'Playback speed (1 = real time, 0.5 = half speed, 2 = double speed):'};
    % Use enough precision that the dialog's own defaults always fall inside
    % the exact workbook limits.
    defaults = {sprintf('%.6f', availableStart), sprintf('%.6f', availableEnd), '1'};
    answer = inputdlg(prompts, [testId ' animation options'], [1 72], defaults);
    if isempty(answer), output = []; return; end

    startTime = str2double(answer{1});
    endTime = str2double(answer{2});
    speed = str2double(answer{3});
    if any(~isfinite([startTime, endTime, speed]))
        error('Beginning time, ending time, and speed must be valid numbers.');
    end
    % Permit boundary values within one data sample. In particular, users can
    % naturally enter trajectory time 0 for the clap even when the first stored
    % result occurs a fraction of a frame later (test11 begins at 0.0141 s).
    if startTime < availableStart - sampleTolerance || endTime > availableEnd + sampleTolerance
        error('Choose times within the available range %.3f to %.3f s.', availableStart, availableEnd);
    end
    startTime = max(startTime, availableStart);
    endTime = min(endTime, availableEnd);
    if startTime >= endTime, error('Ending time must be greater than beginning time.'); end
    if speed <= 0, error('Playback speed must be greater than zero.'); end

    filename = sprintf('%s_animation_t%s_to_%s_x%s.mp4', testId, ...
        filename_number(startTime), filename_number(endTime), filename_number(speed));
    fprintf('Creating %s\n', filename);
    fprintf('Selected trajectory %.3f to %.3f s; synced-video %.3f to %.3f s; speed %.3fx.\n', ...
        startTime, endTime, startTime + 2, endTime + 2, speed);

    output = process_session_results(testId, ...
        'StartTime', startTime, ...
        'EndTime', endTime, ...
        'PlaybackSpeed', speed, ...
        'TrailSeconds', 5, ...
        'OutputFrameRate', 10, ...
        'MakeVideo', true, ...
        'MakeStaticPlots', false, ...
        'Visible', false, ...
        'VideoFilename', filename);
end

function testId = normalize_test_id(value)
    if isnumeric(value)
        validateattributes(value, {'numeric'}, {'scalar', 'integer', 'nonnegative'});
        testId = sprintf('test%02d', value);
        return;
    end
    token = regexp(strtrim(lower(char(string(value)))), '^(?:test)?(\d+)$', 'tokens', 'once');
    if isempty(token), error('Test must be a number such as 11, ''11'', or ''test11''.'); end
    testId = sprintf('test%02d', str2double(token{1}));
end

function text = filename_number(value)
    text = regexprep(sprintf('%.3f', value), '0+$', '');
    text = regexprep(text, '\.$', '');
    text = strrep(text, '-', 'm');
    text = strrep(text, '.', 'p');
end
