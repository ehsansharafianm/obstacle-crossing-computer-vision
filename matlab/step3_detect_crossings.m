clc
clear all
close all
addpath(fileparts(mfilename('fullpath')));

%% ========================================================================
%% STEP 3 - DETECT_CROSSINGS (script) - leading/trailing leg per obstacle crossing
%% ========================================================================
% Uses the CAMERA marker trajectory to detect, for every obstacle-crossing pass,
% which leg leads and which trails, and the cycle's begin/end time - so you no
% longer need the app/Excel leading-trailing labelling.
%
% Run it, enter the test NUMBER (e.g. 101). Reads the REFINED trajectory
%   results/sessions/testN/testN_trajectory_refined.xlsx   (falls back to raw)
% and writes  results/sessions/testN/testN_crossings.xlsx.
%
% How it works (obstacle CENTRE is y = 0):
%   - a "pass" = one contiguous burst of camera data (a lap through the volume);
%   - a real crossing ONLY happens when the OBSTACLE marker is present in the burst -
%     if the obstacle is not seen, no obstacle was on the path, so the burst is
%     skipped (a return walk / turn / gesture, not a crossing);
%   - within a real pass, each foot's TOE crosses y = 0 once -> LEADING = the foot
%     that crosses first, TRAILING = the other;
%   - begin/end = when the markers exist for that pass (the burst extent).
% Obstacle type: the protocol is trials (a run of laps on the same obstacle). After the
% figures open, the script walks you through it ONE TRIAL AT A TIME - enter each trial on
% one line as  [start end] = code  (code = [width][height]) - filling obstacle_code /
% width / height in the Excel, then prints a trial summary. The per-cycle obstacle height
% (obst_z) is printed to show the trial edges (and is on the Z panel of the overview figure).
% Times are the camera clock (time_s); use them in the IMU analysis as a new
% segmentation input after syncing.
%
% FIGURES: (1) a TOTAL-TIME overview - X/Y/Z vs the whole session (feet + obstacle,
% styled like step 1) with every detected crossing marked, and (2) an interactive
% per-pass verification viewer.

%% ===================== SETTINGS =====================
GAP_S    = 0.40;   % a gap longer than this (s) ends a pass/burst
MIN_EXC  = 300;    % a real crossing: the toe swings beyond +/- this in y (mm)
MIN_PASS_S = 0.8;  % ignore bursts shorter than this (s)
CROSS_MARKER = 'toe';   % foot point used for the y=0 crossing ('toe' or 'heel')
MIN_OBST_FRAC = 0.05;   % obstacle must be visible in >= this fraction of a burst
                        % (no obstacle in view -> no real crossing -> skip)
COPY_TO_ANALYSIS = true;   % also save the crossings file into the IMU project's results
ANALYSIS_RESULTS = '';     % '' = auto (.../obstacle-crossing-project/Results/Parameters Output/Test N)

%% ===================== INPUT + LOAD =====================
tn = input('  Input Test Number: ');
id   = ['test' num2str(tn)];
root = fileparts(fileparts(mfilename('fullpath')));            % repo root
sdir = fullfile(root,'results','sessions',id);
f_ref = fullfile(sdir,[id '_trajectory_refined.xlsx']);
f_raw = fullfile(sdir,[id '_trajectory.xlsx']);
if     exist(f_ref,'file'), datafile = f_ref;
elseif exist(f_raw,'file'), datafile = f_raw; warning('No refined file; using raw %s', f_raw);
else,  error('No trajectory file for %s in %s', id, sdir); end
fprintf('Reading: %s\n', datafile);
T  = readtable(datafile,'Sheet','markers','VariableNamingRule','preserve');
vn = string(T.Properties.VariableNames);
t  = T{:, find(startsWith(lower(vn),'time'),1)};  t = t(:);
fs = 1/median(diff(t),'omitnan');
% all four foot markers as [x y z] (mm) - used by the verification viewer
MK = {'L_toe','L_heel','R_toe','R_heel'};
M = struct();
for i = 1:numel(MK)
    m = MK{i};
    M.(m) = [col(T, string(m)+"_x_mm"), col(T, string(m)+"_y_mm"), col(T, string(m)+"_z_mm")];
end
Ly = M.(['L_' char(CROSS_MARKER)])(:,2); Lz = M.(['L_' char(CROSS_MARKER)])(:,3);
Ry = M.(['R_' char(CROSS_MARKER)])(:,2); Rz = M.(['R_' char(CROSS_MARKER)])(:,3);
% obstacle markers (for the presence gate + the total-time overview plot)
OB = struct();
for m = {'obstacle1','obstacle2'}
    mm = m{1};
    OB.(mm) = [col(T, string(mm)+"_x_mm"), col(T, string(mm)+"_y_mm"), col(T, string(mm)+"_z_mm")];
end
obVis = isfinite(OB.obstacle1(:,1)) | isfinite(OB.obstacle2(:,1));   % obstacle seen this frame

%% ===================== DETECT PASSES (data bursts) =====================
val = isfinite(Ly) | isfinite(Ry);          % either foot visible
vi  = find(val);
if isempty(vi), error('No %s marker data in %s.', CROSS_MARKER, id); end
brk = find(diff(vi) > round(GAP_S*fs));
bStart = [vi(1); vi(brk+1)];  bEnd = [vi(brk); vi(end)];

P = struct('pass',{},'begin_s',{},'end_s',{},'dur_s',{},'lead',{},'trail',{}, ...
           'lead_cross_s',{},'trail_cross_s',{},'L_peakz',{},'R_peakz',{},'obst_z',{}, ...
           'begin_row',{},'end_row',{},'flag',{});
nNoObst = 0;   % bursts skipped because the obstacle was not in view (no real crossing)
for k = 1:numel(bStart)
    a = bStart(k); b = bEnd(k);
    if t(b)-t(a) < MIN_PASS_S, continue; end
    if mean(obVis(a:b)) < MIN_OBST_FRAC   % obstacle not present -> not a real crossing
        nNoObst = nNoObst + 1; continue;
    end
    tb = t(a:b);
    ctL = footCross(tb, Ly(a:b), MIN_EXC);
    ctR = footCross(tb, Ry(a:b), MIN_EXC);
    if isnan(ctL) && isnan(ctR), continue; end       % no real crossing -> skip
    % leading = earlier crossing (NaN sorts last)
    if xor(isnan(ctL), isnan(ctR))
        if ~isnan(ctL), lead='L'; lct=ctL; tct=NaN; else, lead='R'; lct=ctR; tct=NaN; end
        trail = otherLeg(lead); flag = 'one foot only';
    elseif ctL <= ctR
        lead='L'; trail='R'; lct=ctL; tct=ctR; flag='';
    else
        lead='R'; trail='L'; lct=ctR; tct=ctL; flag='';
    end
    e = numel(P)+1;
    P(e).pass = e; P(e).begin_s = t(a); P(e).end_s = t(b); P(e).dur_s = t(b)-t(a);
    P(e).lead = lead; P(e).trail = trail; P(e).lead_cross_s = lct; P(e).trail_cross_s = tct;
    P(e).L_peakz = mx(Lz(a:b)); P(e).R_peakz = mx(Rz(a:b));
    P(e).obst_z  = median([OB.obstacle1(a:b,3); OB.obstacle2(a:b,3)],'omitnan');  % obstacle height this pass
    P(e).begin_row = a; P(e).end_row = b; P(e).flag = flag;
end
nP = numel(P);
% flag unusually long passes (e.g. the start raise-gesture region)
durs = [P.dur_s]; medDur = median(durs);
for e = 1:nP, if P(e).dur_s > 3*medDur, P(e).flag = strtrim([P(e).flag ' long-burst(check)']); end, end
fprintf('\nDetected %d passes (median duration %.1f s).  Leading: %d L / %d R.\n', ...
        nP, medDur, sum(strcmp({P.lead},'L')), sum(strcmp({P.lead},'R')));
fprintf('Skipped %d burst(s) with no obstacle in view (not real crossings).\n', nNoObst);

%% ===================== PRINT =====================
fprintf('\n%4s %8s %8s %6s %5s %5s %9s %9s %7s\n','pass','begin','end','dur','lead','trail','Lpeakz','Rpeakz','flag');
for e = 1:nP
    fprintf('%4d %8.1f %8.1f %6.1f %5s %5s %9.0f %9.0f  %s\n', P(e).pass, P(e).begin_s, P(e).end_s, ...
        P(e).dur_s, P(e).lead, P(e).trail, P(e).L_peakz, P(e).R_peakz, P(e).flag);
end

%% ===================== TOTAL-TIME OVERVIEW (X/Y/Z vs whole session) =====================
% Same X/Y/Z-vs-time layout as step 1, but over the ENTIRE session with every
% detected crossing marked: each pass shaded, and on Y the leading (star) and
% trailing (square) y=0 crossings coloured by leading foot.
f2  = figure('Color','w','Name',sprintf('Crossings overview | %s', id),'Position',[80 60 1180 820]);
nmO = {'X - lateral (mm)','Y - walking, 0 = obstacle (mm)','Z - height (mm)'};
cCol = struct('L_toe',[0.55 0.20 0.75],'L_heel',[0.15 0.65 0.20], ...
              'R_toe',[0.95 0.40 0.70],'R_heel',[0.10 0.60 0.60], ...
              'obstacle1',[0.90 0.15 0.15],'obstacle2',[0.60 0.08 0.08]);
axO = gobjects(1,3);
for a = 1:3
    axO(a) = subplot(3,1,a); hold(axO(a),'on'); grid(axO(a),'on'); box(axO(a),'on');
    % shade each detected pass (behind the traces)
    for e = 1:nP, xregion(axO(a), P(e).begin_s, P(e).end_s, 'FaceColor',[0.75 0.80 0.90],'FaceAlpha',0.25); end
    % feet as lines
    for m = {'L_toe','L_heel','R_toe','R_heel'}
        mm = m{1}; lw = 1.6; if endsWith(mm,'heel'), lw = 0.9; end
        plot(axO(a), t, M.(mm)(:,a), '-', 'Color', cCol.(mm), 'LineWidth', lw);
    end
    % obstacle as points
    for m = {'obstacle1','obstacle2'}
        mm = m{1}; plot(axO(a), t, OB.(mm)(:,a), '.', 'Color', cCol.(mm), 'MarkerSize', 4);
    end
    ylabel(axO(a), nmO{a}, 'FontWeight','bold');
    if a == 2   % walking axis: obstacle line + all crossings + per-cycle text
        yline(axO(a), 0, 'k-','LineWidth',1.0);
        for e = 1:nP
            if ~isnan(P(e).lead_cross_s),  plot(axO(a), P(e).lead_cross_s,  0, 'p','Color',leadColor(P(e).lead), 'MarkerFaceColor',leadColor(P(e).lead), 'MarkerEdgeColor','k','MarkerSize',12); end
            if ~isnan(P(e).trail_cross_s), plot(axO(a), P(e).trail_cross_s, 0, 's','Color',leadColor(P(e).trail),'MarkerFaceColor',leadColor(P(e).trail),'MarkerEdgeColor','k','MarkerSize',7); end
            % label: cycle number + leading->trailing leg, written vertically
            % above the pass (vertical so adjacent cycles don't overlap)
            xmid = 0.5*(P(e).begin_s + P(e).end_s);
            txt  = sprintf('#%d  %s\\rightarrow%s', P(e).pass, P(e).lead, P(e).trail);
            text(axO(a), xmid, 2100, txt, 'Rotation',90, 'HorizontalAlignment','left', ...
                 'VerticalAlignment','middle', 'FontSize',7, 'FontWeight','bold', ...
                 'Color', leadColor(P(e).lead), 'Clipping','on');
        end
        ylim(axO(a), [-2600 4300]);   % headroom for the vertical cycle labels
    end
end
xlabel(axO(3),'time (s, camera clock)','FontWeight','bold');
title(axO(1), sprintf('%s - full session  |  %d crossings (shaded)  |  label = #cycle, lead\\rightarrowtrail  |  star = leading y=0, square = trailing (blue=L, red=R lead)', id, nP), 'FontWeight','bold');
tv = t(isfinite(Ly) | isfinite(Ry)); if ~isempty(tv), xlim(axO(1), [min(tv) max(tv)]); end
linkaxes(axO,'x');
exportgraphics(f2, fullfile(sdir,[id '_crossings_timeline.png']), 'Resolution', 150);
fprintf('Saved %s\n', fullfile(sdir,[id '_crossings_timeline.png']));

%% ===================== PER-PASS VERIFICATION VIEWER =====================
buildPassViewer(t, M, P, id);
fprintf('Opened the per-pass verification viewer (Prev/Next or pick a pass).\n');
drawnow;   % make sure all figures are on screen before the labeling prompt

%% ===================== INTERACTIVE OBSTACLE LABELING (step by step) =====================
% Guided, ONE TRIAL AT A TIME. Each trial = the run of consecutive cycles that used the
% same obstacle. Enter each trial on one line as  [start end] = code . A cycle table with
% each cycle's obstacle HEIGHT is printed first, to show where each trial begins/ends.
code = repmat({''},nP,1); wd = code; ht = code;    % blank = unlabeled
fprintf('\n========================= OBSTACLE LABELING =========================\n');
fprintf('Each TRIAL = the cycles that used the SAME obstacle. Enter one trial per line as:\n');
fprintf('     [start finish]=code        (example:  [a b]=c )\n');
fprintf('        code = [width][height]:  width 1 = 5 cm , 2 = 15 cm\n');
fprintf('                                 height 1 = 10%% , 2 = 20%% , 3 = 30%% of leg length\n');
fprintf('   Enter (empty line) = finish labeling and save.   q = exit without saving.\n');
fprintf('\nTip: the "obst_z" column below is the measured obstacle height - it jumps\n');
fprintf('     between trials (>> marks a jump), so it shows you where each trial is.\n');
printCycleGuide(P);
trialN = 0;  trials = zeros(0,3);   % [start end codeNum] per accepted trial (for the summary)
while true
    rem = find(cellfun(@isempty,code));
    fprintf('\n===== TRIAL %d =====   cycles not yet labeled: %s\n', trialN+1, rangeStr(rem));
    [ab, c, act] = askTrial(sprintf('   Trial %d - [start finish]=code  (Enter=finish, q=exit): ', trialN+1), nP);
    if strcmp(act,'quit')
        fprintf('\nLabeling exited (q) - no labels written this run. Re-run step 3 to label.\n');
        return;
    end
    if strcmp(act,'finish'), break; end
    a = ab(1); b = ab(2);
    % Guard: warn before overwriting cycles that are already labeled (a common
    % typo is starting the range too low, e.g. [16 31] instead of [26 31], which
    % silently overwrites earlier trials). Suggest the next unlabeled cycle.
    clash = intersect(a:b, find(~cellfun(@isempty,code)));
    if ~isempty(clash)
        nextfree = min(find(cellfun(@isempty,code))); %#ok<MXFND>
        fprintf('   ! cycles %s are ALREADY labeled', rangeStr(clash));
        if ~isempty(nextfree), fprintf(' - did you mean to start at %d?', nextfree); end
        fprintf('\n');
        if ~strcmpi(strtrim(input('     Overwrite them anyway? (y/N): ','s')),'y')
            fprintf('     Skipped - re-enter this trial.\n'); continue;
        end
    end
    for k = a:b, code{k}=c; wd{k}=c(1); ht{k}=c(2); end
    trialN = trialN + 1;  trials(trialN,:) = [a b str2double(c)]; %#ok<AGROW>
    fprintf('   -> Trial %d = cycles %d-%d, obstacle %s  (width %s, height %s).\n', trialN, a, b, c, c(1), c(2));
    if all(~cellfun(@isempty,code))
        fprintf('\nAll %d cycles are labeled.\n', nP);
        if ~strcmpi(strtrim(input('   Add or correct another trial? (y/N): ','s')),'y'), break; end
    end
end

% ---- summary of the trials you entered ----
fprintf('\n===== TRIAL SUMMARY =====\n');
if trialN == 0
    fprintf('  (no trials labeled)\n');
else
    fprintf('%6s  %-12s  %6s  %6s  %7s\n','trial','cycles','code','width','height');
    for i = 1:trialN
        c = sprintf('%d', trials(i,3));
        fprintf('%6d  %-12s  %6s  %6s  %7s\n', i, sprintf('%d-%d',trials(i,1),trials(i,2)), c, c(1), c(2));
    end
end
fprintf('\nFinal labels:\n');
fprintf('%4s %8s %8s %6s %8s %6s\n','pass','begin','end','lead','obst_z','code');
for e = 1:nP
    fprintf('%4d %8.1f %8.1f %5s>%s %8.0f %6s\n', e, P(e).begin_s, P(e).end_s, ...
        P(e).lead, P(e).trail, P(e).obst_z, dash(code{e}));
end
nlab = nnz(~cellfun(@isempty,code));
if nlab < nP, fprintf('(%d of %d labeled; the rest stay blank - re-run to add them.)\n', nlab, nP); end

% annotate the overview with the obstacle code under each cycle number, then re-save
for e = 1:nP
    if ~isempty(code{e})
        text(axO(2), 0.5*(P(e).begin_s+P(e).end_s), 1650, code{e}, 'Rotation',90, ...
             'HorizontalAlignment','left','VerticalAlignment','middle','FontSize',7, ...
             'FontWeight','bold','Color',[0 0 0],'Clipping','on');
    end
end
exportgraphics(f2, fullfile(sdir,[id '_crossings_timeline.png']), 'Resolution', 150);

%% ===================== SAVE (labeled) =====================
Tout = table([P.pass]', [P.begin_s]', [P.end_s]', [P.dur_s]', {P.lead}', {P.trail}', ...
             [P.lead_cross_s]', [P.trail_cross_s]', [P.L_peakz]', [P.R_peakz]', [P.obst_z]', ...
             [P.begin_row]', [P.end_row]', code, wd, ht, {P.flag}', ...
    'VariableNames', {'pass','begin_s','end_s','dur_s','lead_leg','trail_leg', ...
    'lead_cross_s','trail_cross_s','L_peakz_mm','R_peakz_mm','obst_z_mm','begin_row','end_row', ...
    'obstacle_code','width','height','flag'});
outXls = fullfile(sdir, [id '_crossings.xlsx']);
if exist(outXls,'file'), delete(outXls); end
writetable(Tout, outXls, 'Sheet','crossings');
nlab = nnz(~cellfun(@isempty,code));
fprintf('\nSaved (CV project):\n  %s  (%d of %d cycles labeled).\n', outXls, nlab, nP);

% ---- also save into the IMU project's results (Parameters Output/Test N) ----
if COPY_TO_ANALYSIS
    ar = ANALYSIS_RESULTS;
    if isempty(ar)
        docs = fileparts(fileparts(mfilename('fullpath')));            % .../obstacle-crossing-computer-vision
        docs = fileparts(docs);                                        % .../Documents
        ar = fullfile(docs,'obstacle-crossing-project','Results','Parameters Output',['Test ' num2str(tn)]);
    end
    if ~isfolder(ar), mkdir(ar); end
    dst = fullfile(ar, [id '_crossings.xlsx']);
    [ok,msg] = copyfile(outXls, dst);
    if ok, fprintf('Saved (IMU project):\n  %s\n', dst);
    else,  warning('IMU-project copy failed (%s). Target: %s', msg, dst); end
end
fprintf('Done.\n');

%% ========================================================================
%  LOCAL FUNCTIONS
%% ========================================================================
function v = col(T, name)
    vn = string(T.Properties.VariableNames); j = find(vn == name, 1);
    if isempty(j), v = nan(height(T),1); else, v = T{:,j}; end
end
function m = mx(x), if any(isfinite(x)), m = max(x,[],'omitnan'); else, m = NaN; end, end
function s = otherLeg(s0), if s0=='L', s='R'; else, s='L'; end, end
function c = leadColor(s), if s=='L', c=[0.20 0.45 0.80]; else, c=[0.85 0.25 0.20]; end, end
function s = dash(x), if isempty(x), s='-'; else, s=x; end, end

function [ab, code, act] = askTrial(prompt, nP)
% Parse one trial line "[start finish]=code" (brackets optional; a single cycle also OK,
% e.g. "[7 7]=21" or "7=21"). Returns ab=[start finish] (start<=finish, within 1..nP),
% code = the two-digit string, and act = 'trial'. Empty line -> act='finish'; typing
% q/quit/exit -> act='quit'. Loops until the entry is valid.
    ab = []; code = ''; act = 'finish';
    while true
        s = strtrim(input(prompt,'s'));
        if isempty(s), act = 'finish'; return; end
        if any(strcmpi(s, {'q','quit','exit','esc'})), act = 'quit'; return; end
        parts = regexp(s, '=', 'split');
        if numel(parts) ~= 2, fprintf('   ! use the form  [start finish]=code  (example: [a b]=c)\n'); continue; end
        nums = str2double(regexp(parts{1}, '\d+', 'match'));
        code = strtrim(parts{2});
        if isempty(nums) || any(isnan(nums)) || numel(nums) > 2
            fprintf('   ! the left side needs the cycle range, e.g.  [10 20]\n'); continue;
        end
        if isempty(regexp(code, '^\d\d$', 'once'))
            fprintf('   ! the code must be two digits (width then height)\n'); continue;
        end
        if isscalar(nums), a = nums; b = nums; else, a = min(nums); b = max(nums); end
        if a < 1 || b > nP, fprintf('   ! cycles must be within 1-%d\n', nP); continue; end
        ab = [a b]; act = 'trial'; return;
    end
end

function s = rangeStr(idx)
% Compress a sorted list like [1 2 3 5 6] into "1-3,5-6" (or "none").
    idx = idx(:)';
    if isempty(idx), s = 'none'; return; end
    d = [true, diff(idx)~=1]; starts = idx(d); ends = idx([d(2:end), true]);
    parts = strings(1,numel(starts));
    for i = 1:numel(starts)
        if starts(i)==ends(i), parts(i) = sprintf('%d',starts(i));
        else,                  parts(i) = sprintf('%d-%d',starts(i),ends(i)); end
    end
    s = char(strjoin(parts,','));
end

function printCycleGuide(P)
% Print a per-cycle table with the obstacle height, flagging where the height jumps
% (a likely block boundary) with ">>".
    nP = numel(P);
    fprintf('\n%4s %8s %8s %7s %8s  %s\n','pass','begin','end','lead','obst_z','(height jump)');
    prevz = NaN;
    for e = 1:nP
        z = P(e).obst_z; mark = '';
        if ~isnan(prevz) && ~isnan(z) && abs(z-prevz) > 40, mark = '>> height changed (new trial?)'; end
        fprintf('%4d %8.1f %8.1f %6s>%s %8.0f  %s\n', e, P(e).begin_s, P(e).end_s, ...
            P(e).lead, P(e).trail, z, mark);
        prevz = z;
    end
end

function buildPassViewer(t, M, P, id)
% Step through each detected pass and check the detection: X/Y/Z of both feet
% (toe solid, heel dashed; Left blue, Right red) over the cycle window, with the
% cycle begin/end lines and the leading/trailing y=0 crossings marked.
    nP = numel(P);
    hF = figure('Color','w','Name',sprintf('Verify crossings | %s', id),'Position',[60 70 1200 820]);
    ax = gobjects(1,3); nm = {'X - lateral','Y - walking (0 = obstacle)','Z - height'};
    for a = 1:3
        ax(a) = axes(hF,'Position',[0.30 0.09+(3-a)*0.30 0.66 0.255]); hold(ax(a),'on'); grid(ax(a),'on'); box(ax(a),'on');
        ylabel(ax(a), [nm{a} ' (mm)'], 'FontWeight','bold');
    end
    xlabel(ax(3),'time (s, camera clock)','FontWeight','bold');
    LX = 0.02;
    uicontrol(hF,'Style','pushbutton','Units','normalized','Position',[LX 0.945 0.06 0.035],'String','< Prev','Callback',@(~,~) stepPass(hF,-1));
    uicontrol(hF,'Style','pushbutton','Units','normalized','Position',[LX+0.065 0.945 0.06 0.035],'String','Next >','Callback',@(~,~) stepPass(hF,+1));
    uicontrol(hF,'Style','text','Units','normalized','Position',[LX 0.905 0.22 0.025],'String','Pick a pass:','BackgroundColor','w','HorizontalAlignment','left','FontWeight','bold');
    lbl = arrayfun(@(e) sprintf('%d: %s lead  (%.0f s)', P(e).pass, P(e).lead, P(e).begin_s), 1:nP, 'uni', 0);
    lb = uicontrol(hF,'Style','listbox','Units','normalized','Position',[LX 0.06 0.22 0.845],'String',lbl,'Value',1,'Callback',@(~,~) pickPass(hF));
    S = struct('ax',ax,'t',t,'M',M,'P',P,'nP',nP,'lb',lb,'cur',1);
    guidata(hF,S); showPass(hF,1);
end
function stepPass(hF,d)
    S = guidata(hF); e = min(max(S.cur+d,1),S.nP); set(S.lb,'Value',e); showPass(hF,e);
end
function pickPass(hF)
    S = guidata(hF); showPass(hF, get(S.lb,'Value'));
end
function showPass(hF, e)
    S = guidata(hF); S.cur = e; guidata(hF,S); P = S.P(e); t = S.t;
    cL = [0.20 0.45 0.80]; cR = [0.85 0.25 0.20];
    pad = 0.7; w = t >= P.begin_s-pad & t <= P.end_s+pad;
    for a = 1:3
        cla(S.ax(a)); hold(S.ax(a),'on');
        plot(S.ax(a), t(w), S.M.L_toe(w,a),  '-',  'Color',cL,'LineWidth',1.8);
        plot(S.ax(a), t(w), S.M.L_heel(w,a), '--', 'Color',cL,'LineWidth',1.0);
        plot(S.ax(a), t(w), S.M.R_toe(w,a),  '-',  'Color',cR,'LineWidth',1.8);
        plot(S.ax(a), t(w), S.M.R_heel(w,a), '--', 'Color',cR,'LineWidth',1.0);
        xline(S.ax(a), P.begin_s, '-',  'begin','Color',[0 0.6 0],'LineWidth',1.4,'LabelVerticalAlignment','bottom','Interpreter','none');
        xline(S.ax(a), P.end_s,   '-',  'end',  'Color',[0.6 0 0.6],'LineWidth',1.4,'LabelVerticalAlignment','bottom','Interpreter','none');
        if a == 2   % Y axis: obstacle line + the y=0 crossings
            yline(S.ax(a), 0, 'k-','LineWidth',1.0);
            cLead = leadColor(P.lead);  cTrail = leadColor(P.trail);
            if ~isnan(P.lead_cross_s),  plot(S.ax(a), P.lead_cross_s, 0,  'p','Color',cLead,'MarkerFaceColor',cLead,'MarkerEdgeColor','k','MarkerSize',16); end
            if ~isnan(P.trail_cross_s), plot(S.ax(a), P.trail_cross_s,0,  's','Color',cTrail,'MarkerFaceColor',cTrail,'MarkerEdgeColor','k','MarkerSize',11); end
        end
        xlim(S.ax(a), [P.begin_s-pad, P.end_s+pad]);
    end
    ttl = sprintf('%s  |  Pass %d/%d   LEAD = %s , TRAIL = %s   (dur %.1f s)   %s', id_of(hF), e, S.nP, P.lead, P.trail, P.dur_s, P.flag);
    title(S.ax(1), ttl, 'FontWeight','bold','Interpreter','none');
    legend(S.ax(1), {'L toe','L heel','R toe','R heel'}, 'Location','eastoutside','FontSize',8);
end
function s = id_of(hF), nm = get(hF,'Name'); s = extractAfter(nm,'| '); end

function ct = footCross(tb, y, minExc)
% Time the toe crosses y=0 within this burst: pick the sign change whose swing
% reaches beyond +/- minExc on both sides (a real walking pass), nearest the burst
% centre; linear-interpolate the exact zero time. NaN if no such crossing.
    ct = NaN;
    ok = isfinite(y);
    if nnz(ok) < 3, return; end
    ti = tb(ok); yi = y(ok);
    if ~(min(yi) < -minExc && max(yi) > minExc), return; end   % foot must span both sides
    sc = find(yi(1:end-1) .* yi(2:end) < 0);                   % sign changes (0-crossings)
    if isempty(sc), return; end
    [~, pick] = min(abs(ti(sc) - median(ti)));  k = sc(pick);  % the one nearest burst centre
    y1 = yi(k); y2 = yi(k+1); t1 = ti(k); t2 = ti(k+1);
    ct = t1 + (0 - y1)/(y2 - y1) * (t2 - t1);
end
