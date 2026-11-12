import "daisyui/components/badge.css";
import "daisyui/components/collapse.css";
import "daisyui/components/table.css";
import type { AssessmentPayload, CurvesPayload, MeasurementMap, StatusKey } from "../contract/types";
import { Curves, curveColors } from "./Curves";
import "./assessment.css";

const STATUS: Record<StatusKey, [string, string]> = {
  approved: ["Approved", "badge-success"],
  review: ["Review", "badge-warning"],
  rejected: ["Rejected", "badge-error"],
  inconclusive: ["Inconclusive", "badge-neutral"],
};

function Verdict({ status }: { status: StatusKey }) {
  const [label, tone] = STATUS[status];
  return <span className={`badge badge-soft badge-sm ${tone}`}>{label}</span>;
}

function RegionMap({ map }: { map: MeasurementMap }) {
  const size = map.block_size;

  return (
    <section className="assessment-map" aria-label="Where noise was measured">
      <h3>Where noise was measured</h3>
      <figure>
        <svg viewBox={`0 0 ${map.width} ${map.height}`} role="img" aria-label={map.caption}>
          <image href={map.url} width={map.width} height={map.height} preserveAspectRatio="none" />
          {map.blocks.map(block => (
            <rect key={`${block.x},${block.y}`} x={block.x} y={block.y} width={size} height={size} className="assessment-block" />
          ))}
        </svg>
        <figcaption className="assessment-map-key">
          <span><i className="assessment-swatch-pixels" />Pixels used</span>
          <span><i className="assessment-swatch-block" />Accepted block</span>
        </figcaption>
      </figure>
      <p>{map.blocks.length} blocks of {size} × {size} px · {map.pixel_count.toLocaleString("en-US")} unique pixels used</p>
      <p className="assessment-rule">A block qualifies with at least {Math.round(100 * map.min_coverage)}% soft-tissue coverage.</p>
    </section>
  );
}

function Spectrum({ curve, compact = false }: { curve: CurvesPayload; compact?: boolean }) {
  const colors = curveColors(curve.series);
  return (
    <>
      {compact && <Curves payload={curve} width={300} height={190} endLabels={false} />}
      <ul className="assessment-legend" aria-label="Chart legend">
        {curve.series.map((series, i) => (
          <li key={i}><span aria-hidden="true" style={{ backgroundColor: colors[i] }} />{series.label}</li>
        ))}
      </ul>
      {!compact && <Curves payload={curve} width={540} height={205} endLabels={false} />}
    </>
  );
}

function Distances({ entry, limits, max }: {
  entry: AssessmentPayload["assessments"][number];
  limits: AssessmentPayload["limits"];
  max: number;
}) {
  const position = (distance: number) => `${100 * distance / max}%`;
  return (
    <section className="assessment-result" aria-label={entry.label}>
      <div className="assessment-heading">
        <h4>{entry.label}</h4>
        <Verdict status={entry.verdict} />
      </div>
      <p>{entry.summary}</p>
      {entry.readings.length > 0 && (
        <dl className="assessment-distances">
          {entry.readings.map(reading => (
            <div className="assessment-distance" key={reading.label}>
              <dt>{reading.label}</dt>
              <dd>
                <div className="assessment-track" aria-hidden="true">
                  <span style={{ width: position(limits.review) }} />
                  <span style={{ width: position(limits.reject - limits.review) }} />
                  <span style={{ width: position(max - limits.reject) }} />
                  <i data-status={reading.status} style={{ left: position(Math.abs(reading.distance)) }} />
                </div>
                <span className="assessment-distance-value">
                  {Math.abs(reading.distance).toFixed(2)} IQR<span className="assessment-sr"> · {STATUS[reading.status][0]}</span>
                </span>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

function Measurements({ entry }: { entry: AssessmentPayload["assessments"][number] }) {
  return (
    <div className="assessment-table" tabIndex={0} role="region" aria-label={`${entry.label} measurements`}>
      <table className="table table-sm">
        <caption>{entry.label}</caption>
        <thead>
          <tr>
            <th scope="col">Measurement</th><th scope="col">Original</th><th scope="col">Synthetic</th>
            <th scope="col">Change</th><th scope="col">Distance</th><th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {entry.readings.map(reading => (
            <tr key={reading.label}>
              <th scope="row">{reading.label}<small>{reading.description}</small></th>
              <td>{reading.original}</td><td>{reading.synthetic}</td><td>{reading.change}</td>
              <td>{Math.abs(reading.distance).toFixed(2)} IQR</td><td><Verdict status={reading.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Assessment({ payload }: { payload: AssessmentPayload }) {
  const measured = payload.assessments.filter(entry => entry.readings.length);
  const max = Math.max(payload.limits.reject + 1,
    ...measured.flatMap(entry => entry.readings.map(reading => Math.ceil(Math.abs(reading.distance)) + .15)));

  return (
    <div className="assessment">
      {(payload.overlay || payload.curve) && (
        <div className="assessment-overview">
          {payload.overlay && <RegionMap map={payload.overlay} />}
          {payload.curve && (
            <section className="assessment-main-spectrum" aria-label={payload.curve_title}>
              <h3>{payload.curve_title}</h3>
              <Spectrum curve={payload.curve} compact />
              <p className="assessment-rule">{payload.curve_hint}</p>
            </section>
          )}
        </div>
      )}
      <section className={payload.overlay || payload.curve ? "assessment-chart" : undefined} aria-label="Noise verdict">
        <h3>Distance from the original</h3>
        {measured.length > 0 && <p className="assessment-rule">{payload.rule}</p>}
        {payload.assessments.map((entry, index) => <Distances key={index} entry={entry} limits={payload.limits} max={max} />)}
      </section>
      {payload.broad_curve && (
        <details className="collapse collapse-arrow assessment-details">
          <summary className="collapse-title">{payload.details_title}</summary>
          <div className="collapse-content">
            <p>{payload.details_hint}</p>
            <Spectrum curve={payload.broad_curve} />
          </div>
        </details>
      )}
      {measured.length > 0 && (
        <details className="collapse collapse-arrow assessment-details">
          <summary className="collapse-title">Measurement tables</summary>
          <div className="collapse-content">
            {measured.map((entry, index) => <Measurements entry={entry} key={index} />)}
          </div>
        </details>
      )}
    </div>
  );
}
