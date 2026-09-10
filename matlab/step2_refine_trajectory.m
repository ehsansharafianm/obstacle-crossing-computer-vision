clc
clear all
close all
addpath(fileparts(mfilename('fullpath')));

%% ========================================================================
%% REFINE_TRAJECTORY (script) - clean reconstructed marker trajectories
%% ========================================================================
% Run it and enter the test NUMBER at the prompt (e.g. 22). Reads
%   results/sessions/testN/testN_trajectory.xlsx  (markers sheet)
% and writes testN_trajectory_refined.xlsx next to it AND into the Analysis
% Data/Camera CV/Test N/ folder. Cleans ALL markers (feet + obstacles):
%   1) DESPIKE  - out-of-volume / height-floor gate + isolated 3D jump gate -> NaN
%   2) GAP-FILL - pchip across gaps <= P.maxGapS (P.fillAllInternal bridges all)
%   3) SMOOTH   - Savitzky-Golay per continuous span (jitter only; peaks kept)
% time_s and the 'audio' sheet are preserved. A QC figure (3D + X/Y/Z vs time)
% opens and a per-marker summary prints. Tune the P block below and re-run.

tn = input('  Input Test Number: ');
id = ['test' num2str(tn)];

    % ===================== PARAMETERS (edit here) =====================
    % The reconstruction already drops far outliers, and the real leg-raise/cross
    % peaks are large & fast, so refinement is GENTLE: only cut clear out-of-volume
    % coords and isolated out-and-back spikes, then fill short gaps and de-jitter.
    P.xyBounds    = [-3000 3000];  % plausible lateral/walking range (mm) -> else glitch
    P.zFloorMM    = 0;     % height floor (mm): Z below this is impossible -> removed & re-filled,
                           %   and the final output is clamped to it (raise ~15-25 to also cut near-floor noise)
    P.zMaxMM      = 1300;  % height ceiling (mm) -> above this is a glitch
    P.jumpMM      = 150;   % isolated 3D per-frame jump (mm) above which a spike is cut
    P.maxGapS     = 0.50;  % fill internal gaps up to this long (s) via pchip; longer -> NaN
    P.fillAllInternal = false;  % true = bridge EVERY internal gap regardless of length
                                %   (fills the long between-pass voids too - use with care:
                                %    it invents motion where the foot was out of view)
    P.smoothWin   = 9;     % smoothing window (samples); set 0 to disable
    P.smoothMeth  = 'sgolay';   % 'sgolay' | 'gaussian' | 'movmean'
    P.useHampel   = false; % optional local despike (OFF: real runs are short & spiky)
    P.hampelWin   = 5;     % Hampel half-window (samples), if enabled
    P.hampelNSig  = 6;     % Hampel reject threshold (robust SDs), if enabled
    P.rigidReport = true;  % report (only) frames where toe<->heel distance is implausible
    P.copyToAnalysis = true;    % also copy the refined file into the Analysis Camera CV folder
    P.analysisCamRoot = '';     % '' = auto (…/Obstacle Crossing Project/Analysis Environment/Data/Camera CV)
    % =================================================================

    %% ---- locate the raw workbook for this test ----
    root = fileparts(fileparts(mfilename('fullpath')));          % repo root
    datafile = fullfile(root,'results','sessions',id,[id '_trajectory.xlsx']);
    if ~exist(datafile,'file')
        alt = fullfile(root,'results','sessions',id,[id '_trajectory.csv']);
        if exist(alt,'file'), datafile = alt;
        else, error('No trajectory file for "%s":\n  %s', id, datafile); end
    end
    isxlsx = endsWith(lower(datafile),'.xlsx');
    if isxlsx, T = readtable(datafile,'Sheet','markers','VariableNamingRule','preserve');
    else,      T = readtable(datafile,'VariableNamingRule','preserve'); end
    vn = string(T.Properties.VariableNames);
    if ~any(vn=="time_s"), error('File needs a time_s column.'); end
    t  = T.time_s;  n = numel(t);
    fs = 1/median(diff(t),'omitnan');
    maxGapFrames = max(1, round(P.maxGapS*fs));
    fprintf('Refine: %s\n  %d frames, ~%.1f Hz, fill gaps <= %d frames (%.2f s)\n', ...
            datafile, n, fs, maxGapFrames, P.maxGapS);

    %% ---- auto-detect markers ----
    markers = {};
    for i = 1:numel(vn)
        tok = regexp(vn(i),'^(.*)_x_mm$','tokens','once');
        if ~isempty(tok), markers{end+1} = char(tok(1)); end %#ok<AGROW>
    end

    %% ---- refine each foot marker ----
    Tref = T;  raw = struct(); ref = struct();  summary = {};
    for k = 1:numel(markers)
        m = markers{k};
        cx = m+"_x_mm"; cy = m+"_y_mm"; cz = m+"_z_mm";
        X = [T.(char(cx)), T.(char(cy)), T.(char(cz))];
        raw.(m) = X;
        % All markers (feet AND obstacles) get outlier removal + fill + smooth.
        Xd = X;  nSpk = 0;
        % 1) physical-bounds gate: out-of-volume coords (incl. sub-floor height) -> NaN
        oB = boundsGate(Xd, P.xyBounds, [P.zFloorMM P.zMaxMM]);  Xd(oB) = NaN;  nSpk = nSpk + nnz(oB);
        % 1b) optional local despike (off by default)
        if P.useHampel
            for a = 1:3
                [Xd(:,a), o1] = hampelNaN(Xd(:,a), P.hampelWin, P.hampelNSig);
                nSpk = nSpk + nnz(o1);
            end
        end
        % 2) 3D isolated-jump gate (out-and-back) -> whole frame NaN
        oj = jumpGate(Xd, P.jumpMM);  Xd(oj,:) = NaN;  nSpk = nSpk + nnz(oj);
        % 3) fill short gaps, then smooth per span
        Xf = Xd; nFill = 0;
        gapLim = maxGapFrames;  if P.fillAllInternal, gapLim = inf; end
        for a = 1:3
            [Xf(:,a), nf] = fillShortRuns(t, Xd(:,a), gapLim);
            nFill = nFill + nf;
            if P.smoothWin > 1, Xf(:,a) = smoothSpans(Xf(:,a), P.smoothWin, P.smoothMeth); end
        end
        % height can't be negative: clamp any residual sub-floor Z (e.g. smoothing
        % overshoot near the ground). NaN stays NaN (NaN < floor is false).
        Xf(Xf(:,3) < P.zFloorMM, 3) = P.zFloorMM;
        ref.(m) = Xf;
        Tref.(char(cx)) = Xf(:,1); Tref.(char(cy)) = Xf(:,2); Tref.(char(cz)) = Xf(:,3);
        nStillNaN = nnz(isnan(Xf(:,3)));
        summary(end+1,:) = {m, nSpk, round(nFill/3), nStillNaN, nnz(isnan(X(:,3)))}; %#ok<AGROW>
    end

    %% ---- rigid-foot diagnostic (report only) ----
    if P.rigidReport
        for side = ["L","R"]
            tn_ = side+"_toe"; hn_ = side+"_heel";
            if isfield(ref,char(tn_)) && isfield(ref,char(hn_))
                d = vecnorm(ref.(char(tn_)) - ref.(char(hn_)), 2, 2);
                dmed = median(d,'omitnan');
                nBad = nnz(abs(d - dmed) > max(0.5*dmed, 40) & isfinite(d));
                fprintf('  Rigid-foot %s: toe-heel = %.0f mm (median); %d frame(s) deviate >50%%.\n', side, dmed, nBad);
            end
        end
    end

    %% ---- summary table ----
    fprintf('\n  %-10s %8s %8s %10s %10s\n','marker','spikes','filled','NaN(ref)','NaN(raw)');
    for r = 1:size(summary,1)
        fprintf('  %-10s %8d %8d %10d %10d\n', summary{r,1}, summary{r,2}, summary{r,3}, summary{r,4}, summary{r,5});
    end

    %% ---- write refined workbook (next to source) ----
    [pdir,base,~] = fileparts(datafile);
    base = regexprep(base,'_trajectory$','');      % strip if present
    outFile = fullfile(pdir, [char(base) '_trajectory_refined.xlsx']);
    if exist(outFile,'file'), delete(outFile); end
    writetable(Tref, outFile, 'Sheet','markers');
    if isxlsx
        sh = sheetnames(datafile);
        for extra = ["audio","obstacle","ground"]
            if any(strcmp(sh,extra))
                writetable(readtable(datafile,'Sheet',char(extra),'VariableNamingRule','preserve'), outFile, 'Sheet', char(extra));
            end
        end
    end
    fprintf('\nSaved refined trajectory:\n  %s\n', outFile);

    %% ---- also copy into the Analysis Camera CV folder (Test N) ----
    if P.copyToAnalysis
        camRoot = P.analysisCamRoot;
        if isempty(camRoot)
            docs = fileparts(fileparts(fileparts(mfilename('fullpath'))));   % .../Documents
            camRoot = fullfile(docs,'Obstacle Crossing Project','Analysis Environment','Data','Camera CV');
        end
        num = regexp(char(base),'(\d+)','match','once');       % test22 -> 22
        if isempty(num)
            warning('Could not read a test number from "%s"; skipped Analysis copy.', char(base));
        else
            dstDir = fullfile(camRoot, ['Test ' num]);
            if ~isfolder(dstDir), mkdir(dstDir); end
            dst = fullfile(dstDir, [char(base) '_trajectory_refined.xlsx']);
            [ok,msg] = copyfile(outFile, dst);
            if ok, fprintf('Copied to Analysis Camera CV:\n  %s\n', dst);
            else,  warning('Analysis copy failed (%s). Target: %s', msg, dst); end
        end
    end

    %% ---- QC figure: raw (faint) vs refined (bold), X/Y/Z vs time ----
    qcFigure(t, markers, raw, ref, base);

%% ======================= LOCAL FUNCTIONS =======================
function [xo, isout] = hampelNaN(x, win, nsig)
% Sliding median +/- nsig*MAD over the finite samples; outliers -> NaN (removed,
% not replaced - the gap-fill step handles them). NaN input stays NaN.
    n = numel(x); xo = x; isout = false(n,1);
    for i = 1:n
        if isnan(x(i)), continue; end
        lo = max(1,i-win); hi = min(n,i+win);
        w = x(lo:hi); w = w(~isnan(w));
        if numel(w) < 3, continue; end
        m = median(w); s = 1.4826*median(abs(w-m));
        if s > 0 && abs(x(i)-m) > nsig*s, xo(i) = NaN; isout(i) = true; end
    end
end

function bad = boundsGate(X, xy, z)
% Per-axis physical-plausibility gate: coordinates outside the capture volume are
% lost-marker/parked glitches. Returns an n x 3 logical (NaN entries -> false).
    bad = false(size(X));
    bad(:,1) = X(:,1) < xy(1) | X(:,1) > xy(2);
    bad(:,2) = X(:,2) < xy(1) | X(:,2) > xy(2);
    bad(:,3) = X(:,3) < z(1)  | X(:,3) > z(2);
    bad(isnan(X)) = false;
end

function bad = jumpGate(X, jmm)
% Flag isolated 3D spikes: a frame that jumps > jmm from BOTH neighbours (out and
% back). Only where the frame and both neighbours are finite.
    n = size(X,1); bad = false(n,1);
    for i = 2:n-1
        if any(isnan(X(i,:))) || any(isnan(X(i-1,:))) || any(isnan(X(i+1,:))), continue; end
        db = norm(X(i,:)-X(i-1,:));  df = norm(X(i,:)-X(i+1,:));  ds = norm(X(i+1,:)-X(i-1,:));
        if db > jmm && df > jmm && ds < max(db,df), bad(i) = true; end
    end
end

function [y, nfill] = fillShortRuns(t, x, maxGapFrames)
% pchip across internal NaN runs no longer than maxGapFrames; leading/trailing
% and long gaps stay NaN. nfill = number of samples filled.
    y = x; nfill = 0; fin = ~isnan(x);
    if nnz(fin) < 2, return; end
    xf = interp1(t(fin), x(fin), t, 'pchip', NaN);   % NaN outside finite range
    n = numel(x); i = 1;
    while i <= n
        if isnan(x(i))
            j = i; while j <= n && isnan(x(j)), j = j+1; end   % NaN run [i, j-1]
            if i > 1 && j <= n && (j-i) <= maxGapFrames        % internal & short
                y(i:j-1) = xf(i:j-1);  nfill = nfill + (j-i);
            end
            i = j;
        else
            i = i+1;
        end
    end
end

function y = smoothSpans(x, win, method)
% Smooth each continuous (non-NaN) run independently, so NaN gaps aren't bridged.
    y = x; n = numel(x); i = 1;
    while i <= n
        if ~isnan(x(i))
            j = i; while j <= n && ~isnan(x(j)), j = j+1; end   % finite run [i, j-1]
            seg = x(i:j-1);
            if numel(seg) >= max(win,3)
                try,   seg = smoothdata(seg, method, win);
                catch, seg = smoothdata(seg, 'movmean', win); end
            end
            y(i:j-1) = seg;  i = j;
        else
            i = i+1;
        end
    end
end

function qcFigure(t, markers, raw, ref, base)
% Two SEPARATE interactive QC windows so each is big and clear:
%   (1) 3D raw-vs-refined,  (2) X/Y/Z-vs-time raw-vs-refined.
% Raw = faint dots, refined = solid line (obstacles as points). Each window has
% per-marker checkboxes + Raw/Refined layer toggles.
    qc3D(markers, raw, ref, base);
    qcTime(t, markers, raw, ref, base);
end

function qc3D(markers, raw, ref, base)
    nM = numel(markers);
    f = figure('Color','w','Name',['Refine QC - 3D - ' char(base)],'Position',[60 90 1060 820]);
    ax = axes(f,'Position',[0.19 0.10 0.78 0.82]); hold(ax,'on'); grid(ax,'on'); box(ax,'on');
    view(ax,3); axis(ax,'equal'); rotate3d(ax,'on');
    xlabel(ax,'X (mm)','FontWeight','bold'); ylabel(ax,'Y (mm)','FontWeight','bold'); zlabel(ax,'Z - height (mm)','FontWeight','bold');
    title(ax, sprintf('3D trajectory - raw (dots) vs refined (line) | %s', char(base)),'FontWeight','bold','Interpreter','none');
    Hr = gobjects(nM,1); Hf = gobjects(nM,1);
    for k = 1:nM
        m = markers{k}; c = qcColor(m); obs = startsWith(m,'obstacle'); R = raw.(m); F = ref.(m);
        Hr(k) = plot3(ax, R(:,1),R(:,2),R(:,3), '.', 'Color',[c 0.30], 'MarkerSize',9);
        if obs, Hf(k) = plot3(ax, F(:,1),F(:,2),F(:,3), 'o','Color',c,'MarkerFaceColor',c,'MarkerSize',7);
        else,   Hf(k) = plot3(ax, F(:,1),F(:,2),F(:,3), '-','Color',c,'LineWidth',2.6); end
    end
    addToggles(f, markers, Hr, Hf);
end

function qcTime(t, markers, raw, ref, base)
    axNames = {'X','Y','Z'};  nM = numel(markers);
    f = figure('Color','w','Name',['Refine QC - vs time - ' char(base)],'Position',[120 70 1360 820]);
    axT = gobjects(1,3);
    for a = 1:3
        axT(a) = axes(f,'Position',[0.19 0.09+(3-a)*0.30 0.78 0.255]); hold(axT(a),'on'); grid(axT(a),'on'); box(axT(a),'on');
        ylabel(axT(a), sprintf('%s (mm)', axNames{a}), 'FontWeight','bold');
    end
    xlabel(axT(3),'time (s)','FontWeight','bold');
    title(axT(1), sprintf('Position vs time - raw (dots) vs refined (line) | %s', char(base)),'FontWeight','bold','Interpreter','none');
    Hr = gobjects(nM,3); Hf = gobjects(nM,3);
    for k = 1:nM
        m = markers{k}; c = qcColor(m); obs = startsWith(m,'obstacle'); R = raw.(m); F = ref.(m);
        for a = 1:3
            Hr(k,a) = plot(axT(a), t, R(:,a), '.', 'Color',[c 0.30], 'MarkerSize',9);
            if obs, Hf(k,a) = plot(axT(a), t, F(:,a), 'o','Color',c,'MarkerFaceColor',c,'MarkerSize',5);
            else,   Hf(k,a) = plot(axT(a), t, F(:,a), '-','Color',c,'LineWidth',2.2); end
        end
    end
    linkaxes(axT,'x');
    addToggles(f, markers, Hr, Hf);
end

function addToggles(f, markers, Hr, Hf)
% Per-marker checkboxes + Raw/Refined layer toggles, stored in the figure.
    nM = numel(markers);
    S.Hr = Hr; S.Hf = Hf; S.nM = nM;
    LX = 0.008; W = 0.11;      % narrow control column on the far left
    % Layers group: 'Layers:' label + Raw + Refined stacked close together
    uicontrol(f,'Style','text','String','Layers','Units','normalized', ...
        'Position',[LX 0.955 W 0.025],'BackgroundColor','w','FontWeight','bold','HorizontalAlignment','left');
    S.cbRaw = uicontrol(f,'Style','checkbox','String','Raw','Value',1,'Units','normalized', ...
        'Position',[LX 0.928 W 0.026],'BackgroundColor','w','FontWeight','bold','Callback',@(~,~) updQC(f));
    S.cbRef = uicontrol(f,'Style','checkbox','String','Refined','Value',1,'Units','normalized', ...
        'Position',[LX 0.902 W 0.026],'BackgroundColor','w','FontWeight','bold','Callback',@(~,~) updQC(f));
    % Markers group
    uicontrol(f,'Style','text','String','Markers','Units','normalized', ...
        'Position',[LX 0.862 W 0.025],'BackgroundColor','w','FontWeight','bold','HorizontalAlignment','left');
    S.cbMk = gobjects(nM,1);
    for k = 1:nM
        S.cbMk(k) = uicontrol(f,'Style','checkbox','String',markers{k},'Value',1,'Units','normalized', ...
            'Position',[LX 0.835-0.030*(k-1) W 0.028],'BackgroundColor','w','FontWeight','bold', ...
            'ForegroundColor',qcColor(markers{k}),'Callback',@(~,~) updQC(f));
    end
    guidata(f,S); updQC(f);
end

function updQC(f)
    S = guidata(f);
    rawOn = S.cbRaw.Value==1; refOn = S.cbRef.Value==1;
    for k = 1:S.nM
        mkOn = S.cbMk(k).Value==1;
        set(S.Hr(k,:), 'Visible', onoff(mkOn && rawOn));
        set(S.Hf(k,:), 'Visible', onoff(mkOn && refOn));
    end
end

function c = qcColor(name)
    switch lower(name)
        case 'l_toe',  c = [0.55 0.20 0.75];
        case 'l_heel', c = [0.15 0.65 0.20];
        case 'r_toe',  c = [0.95 0.40 0.70];
        case 'r_heel', c = [0.10 0.60 0.60];
        otherwise
            if startsWith(lower(name),'obstacle')
                if endsWith(name,'2'), c = [0.60 0.08 0.08]; else, c = [0.90 0.15 0.15]; end
            else, c = [0.3 0.3 0.3]; end
    end
end

function s = onoff(v)
    if v, s = 'on'; else, s = 'off'; end
end
