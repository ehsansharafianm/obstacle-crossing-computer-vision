function plot_validation(id)
% PLOT_VALIDATION  Rigid-wand accuracy validation from a session's marker output.
%
%   plot_validation                 % defaults to 'test21'
%   plot_validation('test21')
%
% Reads results/sessions/<id>/<id>_trajectory.xlsx (the 'markers' sheet), computes
% every pairwise marker-to-marker distance over time (a rigid wand -> each distance
% should be CONSTANT), compares to the KNOWN wand geometry, and reports precision
% (std over time) and accuracy (error vs known). Saves all figures + a CSV to
% results/validation/<id>/.
%
% Markers -> physical colours: L_toe=purple, L_heel=green, R_toe=pink, R_heel=teal.
%
% EDIT the KNOWN distances below for your wand (values in mm, marker-to-marker).

    if nargin < 1 || isempty(id), id = 'test21'; end

    % ===================== KNOWN wand geometry (mm) =====================
    % Marker-to-marker straight-line distances. From the test21 setup:
    %   vertical arm  purple-9-center-19-green   (purple-green collinear = 280)
    %   horiz. arm    center-11-teal-17-pink     (teal-pink direct = 170)
    %   diagonals assume the two arms are perpendicular.
    known = containers.Map();
    known('L_toe|L_heel') = 280;   % purple-green
    known('R_toe|R_heel') = 170;   % pink-teal
    known('L_toe|R_heel') = 142;   % purple-teal
    known('L_heel|R_heel')= 220;   % green-teal
    known('L_toe|R_toe')  = 294;   % purple-pink
    known('L_heel|R_toe') = 338;   % green-pink
    % ====================================================================

    % ---- style (matches plot_trajectory) ----
    S.font='Arial'; S.lbl=20; S.tick=16; S.title=20; S.leg=13; S.lw=2.2; S.box=1.5;

    markers = {'L_toe','L_heel','R_toe','R_heel'};
    labels  = {'purple','green','pink','teal'};
    mcol = [0.55 0.20 0.75; 0.15 0.65 0.20; 0.95 0.40 0.70; 0.10 0.60 0.60];

    % ---- locate files ----
    root = fileparts(fileparts(mfilename('fullpath')));            % repo root
    xlsx = fullfile(root,'results','sessions',id,[id '_trajectory.xlsx']);
    if ~exist(xlsx,'file'), error('No trajectory xlsx:\n  %s', xlsx); end
    outdir = fullfile(root,'results','validation',id);
    if ~exist(outdir,'dir'), mkdir(outdir); end

    % ---- read markers ----
    T = readtable(xlsx,'Sheet','markers'); t = T.time_s;
    P = struct();
    for i = 1:numel(markers)
        m = markers{i};
        P.(m) = [T.([m '_x_mm']), T.([m '_y_mm']), T.([m '_z_mm'])];
    end

    % ---- per-pair distance over time + robust mean/std ----
    prs = nchoosek(1:4, 2); nP = size(prs,1);
    R = struct('key',{},'lbl',{},'col',{},'d',{},'t',{},'mean',{},'std',{},'known',{},'err',{});
    for k = 1:nP
        a = prs(k,1); b = prs(k,2);
        dvec = P.(markers{a}) - P.(markers{b});
        d = sqrt(sum(dvec.^2, 2));
        ok = isfinite(d) & d > 0;
        dk = d(ok); tk = t(ok);
        md = median(dk); keep = abs(dk - md) < 0.3*md;      % drop gross outliers
        key = [markers{a} '|' markers{b}];
        R(k).key=key; R(k).lbl=[labels{a} '-' labels{b}]; R(k).col=(mcol(a,:)+mcol(b,:))/2;
        R(k).d=dk(keep); R(k).t=tk(keep);
        R(k).mean=mean(dk(keep)); R(k).std=std(dk(keep));
        if isKey(known,key), R(k).known=known(key); else, R(k).known=NaN; end
        R(k).err=R(k).mean - R(k).known;
    end

    % ---- console + CSV summary ----
    fprintf('\n%-16s %6s %6s %6s %7s %6s\n','pair','mean','std','known','error','ratio');
    C = cell(nP,6);
    for k=1:nP
        r=R(k); ratio=r.mean/r.known;
        fprintf('%-16s %6.1f %6.1f %6.0f %+7.1f %6.3f\n', r.lbl, r.mean, r.std, r.known, r.err, ratio);
        C(k,:)={r.lbl, r.mean, r.std, r.known, r.err, ratio};
    end
    Tcsv = cell2table(C,'VariableNames',{'pair','mean_mm','std_mm','known_mm','error_mm','ratio'});
    writetable(Tcsv, fullfile(outdir,[id '_distances.csv']));

    % overall fit through origin: measured = slope * known  (slope ~0.94 if under)
    mm = [R.mean]'; kk = [R.known]';
    slope   = (kk' * mm) / (kk' * kk);         % measured per known
    correct = 1/slope;                         % factor to multiply measured -> true
    fprintf('\nOverall: measured is %.1f%% of true (fit slope %.3f); multiply distances by %.4f to correct\n',...
        100*mean(mm./kk), slope, correct);

    delete(findall(0,'Type','figure','Tag',['valfig_' id]));

    % ================= Figure 1: distance vs time (rigidity) =================
    f1 = figure('Name',['Validation ' id ' - distance vs time'],'Color','w',...
                'Tag',['valfig_' id],'Position',[80 90 900 620]);
    ax = axes('Parent',f1); hold(ax,'on'); grid(ax,'on'); box(ax,'on');
    for k=1:nP
        plot(ax, R(k).t, R(k).d, '-', 'Color', R(k).col, 'LineWidth', 1.4);
        yline(ax, R(k).known, '--', 'Color', R(k).col, 'LineWidth', 1.4);
    end
    xlabel(ax,'time (s)','FontSize',S.lbl,'FontName',S.font,'FontWeight','bold');
    ylabel(ax,'marker-marker distance (mm)','FontSize',S.lbl,'FontName',S.font,'FontWeight','bold');
    title(ax,[id ': wand distances over time (solid=measured, dashed=known)'],...
        'FontSize',S.title,'FontName',S.font,'FontWeight','bold');
    legend(ax, {R.lbl}, 'Location','eastoutside','Interpreter','none','FontSize',S.leg);
    set(ax,'FontName',S.font,'FontSize',S.tick,'FontWeight','bold','LineWidth',S.box);
    savefig_(f1, fullfile(outdir,[id '_distance_vs_time.png']));

    % ================= Figure 2: measured vs known (scale) =================
    f2 = figure('Name',['Validation ' id ' - measured vs known'],'Color','w',...
                'Tag',['valfig_' id],'Position',[220 90 700 640]);
    ax = axes('Parent',f2); hold(ax,'on'); grid(ax,'on'); box(ax,'on');
    lim = [0 max(kk)*1.1];
    plot(ax, lim, lim, 'k--', 'LineWidth', 1.5);                       % y = x (perfect)
    plot(ax, lim, slope.*lim, '-', 'Color',[0.85 0.33 0.10], 'LineWidth', 1.8); % measured=slope*known
    for k=1:nP
        errorbar(ax, R(k).known, R(k).mean, R(k).std, 'o', 'Color', R(k).col,...
            'MarkerFaceColor', R(k).col, 'MarkerSize', 9, 'LineWidth', 1.6, 'CapSize',8);
        text(ax, R(k).known+4, R(k).mean, R(k).lbl, 'FontSize',10,'Interpreter','none');
    end
    axis(ax,[lim lim]); axis(ax,'square');
    xlabel(ax,'known distance (mm)','FontSize',S.lbl,'FontName',S.font,'FontWeight','bold');
    ylabel(ax,'measured distance (mm)','FontSize',S.lbl,'FontName',S.font,'FontWeight','bold');
    title(ax,sprintf('%s: measured vs known  (fit slope = %.3f, correct x%.3f)',id,slope,correct),...
        'FontSize',S.title,'FontName',S.font,'FontWeight','bold');
    legend(ax, {'y = x (ideal)', sprintf('best fit (slope %.3f)',slope)}, 'Location','northwest','FontSize',S.leg);
    set(ax,'FontName',S.font,'FontSize',S.tick,'FontWeight','bold','LineWidth',S.box);
    savefig_(f2, fullfile(outdir,[id '_measured_vs_known.png']));

    % ================= Figure 3: per-pair bars (measured +-std vs known) =================
    f3 = figure('Name',['Validation ' id ' - error bars'],'Color','w',...
                'Tag',['valfig_' id],'Position',[360 90 900 560]);
    ax = axes('Parent',f3); hold(ax,'on'); grid(ax,'on'); box(ax,'on');
    x = 1:nP; bw=0.38;
    bar(ax, x-bw/2, mm, bw, 'FaceColor',[0.20 0.50 0.75], 'DisplayName','measured');
    bar(ax, x+bw/2, kk, bw, 'FaceColor',[0.75 0.75 0.75], 'DisplayName','known');
    errorbar(ax, x-bw/2, mm, [R.std], 'k', 'LineStyle','none','LineWidth',1.4,'CapSize',8,'HandleVisibility','off');
    for k=1:nP
        text(ax, x(k), max(mm(k),kk(k))+10, sprintf('%+.0f mm\n(%.1f%%)', R(k).err, 100*(R(k).mean/R(k).known-1)),...
            'HorizontalAlignment','center','FontSize',9);
    end
    set(ax,'XTick',x,'XTickLabel',{R.lbl},'TickLabelInterpreter','none');
    ylabel(ax,'distance (mm)','FontSize',S.lbl,'FontName',S.font,'FontWeight','bold');
    title(ax,[id ': measured (\pmstd) vs known per pair'],'FontSize',S.title,'FontName',S.font,'FontWeight','bold');
    legend(ax,'Location','northwest','FontSize',S.leg);
    set(ax,'FontName',S.font,'FontSize',S.tick,'FontWeight','bold','LineWidth',S.box);
    savefig_(f3, fullfile(outdir,[id '_error_bars.png']));

    fprintf('\nSaved figures + %s_distances.csv -> %s\n', id, outdir);
end

function savefig_(f, pngpath)
    try, exportgraphics(f, pngpath, 'Resolution', 150);
    catch, saveas(f, pngpath); end
end
