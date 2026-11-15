import logoUrl from '../../assets/sparkshield-logo.png';
import { level5 } from '../../domain/levels';
import { downloadManifestCsv, manifestRows } from './reportData';

/**
 * Printable handoff report for the materials/stowage team.
 * Opens over the app; "Print / Save as PDF" uses the browser's print dialog, and the
 * @media print rules in index.css hide everything except this report.
 * Every number comes from the last finished /api/assess result (no new scoring here).
 */

const PSI_SOURCES = [
  ['PSI-69', 'Flame Extinguishment Experiment (FLEX)'],
  ['PSI-25', 'Burning and Suppression of Solids – II (BASS-II)'],
  ['PSI-20', 'ACME – Burning Rate Emulator'],
  ['PSI-99', 'Spacecraft Fire Experiment-II (Saffire-II)'],
  ['PSI-23', 'ACME – Structure and Response of Spherical Diffusion Flames'],
  ['PSI-98', 'Spacecraft Fire Safety Experiment-I (Saffire-I)'],
  ['PSI-100', 'Spacecraft Fire Experiment-III (Saffire-III)'],
];
const psiUrl = (id) => `https://psi.nasa.gov/physci/repo/data/investigations/${id}`;
const LAYOUT_NAMES = { iss: 'ISS-style station', transit: 'Transit spacecraft' };

const fmt = (n) => (n == null ? '—' : Number(n).toFixed(1));
const lvl = (n) => (n == null ? '' : level5(n).label);

export default function ReportView({ planner }) {
  const { layout, layoutKey, mission: M, board, agent, ui, actions } = planner;
  const A = board.assessment;
  const ship = board.ship;
  const B = M.destination;
  const atm = M.atmosphere;
  const date = agent.at ? agent.at.toLocaleString() : new Date().toLocaleString();
  const rows = manifestRows(planner);
  const fixes = layout.modules.flatMap((r) => (board.agentRoom(r)?.fixes || []).map((f) => ({ space: r.name, ...f })));
  const moves = A?.moves || [];

  return (
    <div className="report-overlay" role="dialog" aria-label="Handoff report">
      <div className="report-toolbar no-print">
        <span className="report-toolbar__title">Handoff report</span>
        <div className="spacer" />
        <button className="btn btn--light" onClick={() => downloadManifestCsv(planner)}>Download manifest (CSV)</button>
        <button className="btn btn--brand" onClick={() => window.print()}>Print / Save as PDF</button>
        <button className="btn btn--dark" onClick={actions.closeReport}>Close</button>
      </div>

      <article className="report">
        <header className="report__head">
          <img src={logoUrl} alt="SparkShield" className="report__logo" />
          <div className="flex-1">
            <h1>Stowage fire-risk handoff report</h1>
            <div className="report__meta">
              {LAYOUT_NAMES[layoutKey] || 'Custom hull'} · Assessed {date} · Plan{' '}
              {planner.approved ? `approved (M&P and S&MA sign-off recorded ${planner.approved}, demo)` : 'draft, not yet reviewed'}
              <br />
              Prepared by{' '}
              <input className="report__by" placeholder="your name" value={ui.reportBy || ''} onChange={(e) => actions.setReportBy(e.target.value)} />
              <span className="report__by-print">{ui.reportBy || '—'}</span>
              {A?.inputHash && <> · Assessment ID <span className="mono">{A.inputHash.slice(0, 12)}</span></>}
            </div>
          </div>
        </header>

        <section>
          <h2>Mission conditions {M.confirmed ? '(confirmed)' : '(NOT confirmed by the engineer)'}</h2>
          <table className="report__table">
            <tbody>
              <tr><th>Cruise</th><td>0 g · 14.7 psia · 21% O₂ · {M.preVent} ventilation · {M.pad} days</td></tr>
              <tr><th>Surface</th><td>{B.body} · {B.g} g · {atm.p} psia · {atm.o2}% O₂ · {M.stay} days · {M.eva} EVA-prep periods</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2>Summary</h2>
          <p className="report__score">
            Overall fire risk <strong>{fmt(ship.overall)} / 100 ({lvl(ship.overall)})</strong>
            {' · '}Cruise {fmt(ship.pre)} ({lvl(ship.pre)}) · Surface {fmt(ship.surf)} ({lvl(ship.surf)})
            {ship.driver && <> · driven by {ship.driver === 'pre' ? 'cruise' : 'surface'}</>}
          </p>
          {A?.summary && <p>{A.summary}</p>}
        </section>

        <section>
          <h2>Space by space</h2>
          <table className="report__table">
            <thead>
              <tr><th>Space</th><th>Cruise</th><th>Surface</th><th>Overall</th><th>Detector</th><th>Extinguisher</th></tr>
            </thead>
            <tbody>
              {[...board.ranked, ...layout.modules.filter((r) => !board.ranked.includes(r))].map((r) => {
                const s = board.scores(r);
                const st = board.stats(r);
                return (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{fmt(s.pre)}</td>
                    <td>{fmt(s.surf)}</td>
                    <td><strong>{fmt(s.overall)}</strong> {lvl(s.overall)}</td>
                    <td>{st.det ? 'Yes' : 'No'}</td>
                    <td>{st.ext ? 'Yes' : 'No'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section>
          <h2>Stowage manifest</h2>
          <table className="report__table">
            <thead>
              <tr><th>Space</th><th>Item</th><th>Qty</th><th>Size (cm)</th><th>Type</th><th>Flammability</th><th>Hazard basis</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.space}</td><td>{r.item}</td><td>{r.qty}</td><td className="report__nowrap">{r.size}</td><td>{r.kind}</td><td>{r.hazard}</td><td>{r.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {(fixes.length > 0 || moves.length > 0) && (
          <section>
            <h2>Open actions (not yet applied)</h2>
            <ul>
              {moves.map((m, i) => (
                <li key={`m${i}`}>Move {m.item} ×{m.qty} from {m.from_name} to {m.to_name} (−{m.points} pts). {m.reason}</li>
              ))}
              {fixes.map((f, i) => (
                <li key={`f${i}`}>{f.space}: {f.title}{f.points ? ` (−${f.points} pts)` : ''}. {f.why}</li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h2>Data gaps and limits</h2>
          <ul>
            {(A?.dataGaps || []).map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </section>

        <section>
          <h2>Sources</h2>
          <p>Material hazards come from NASA Physical Sciences Informatics (PSI) microgravity combustion experiments:</p>
          <ul className="report__sources">
            {PSI_SOURCES.map(([id, name]) => (
              <li key={id}>{id} {name}: <a href={psiUrl(id)}>{psiUrl(id)}</a></li>
            ))}
          </ul>
        </section>

        <footer className="report__foot">
          SparkShield · Team GitPushToTheMoon · NASA Space Apps Challenge 2026. Research aid, not a safety certification.
          Scores are computed in code from NASA data; the summary text is AI-written and checked against the data.
        </footer>
      </article>
    </div>
  );
}
