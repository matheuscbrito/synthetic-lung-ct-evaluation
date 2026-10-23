import { toHash, type Route, type View } from "../route";
import { COLOR } from "../status";
import type { Slice, Status, Verdict, Version } from "../api";

const STATUSES: Status[] = ["approved", "review", "rejected", "inconclusive"];
const VIEW_LINKS: { view: View; label: string }[] = [
  { view: "dataset", label: "Dataset" },
  { view: "generators", label: "Generators" },
  { view: "versions", label: "Versions" },
];
const VERDICTS: { verdict: Verdict; label: string }[] = [
  { verdict: "brightness", label: "Brightness" },
  { verdict: "texture", label: "Texture" },
];

interface Props {
  route: Route;
  version: string;
  versions: Version[];
  slices: Slice[] | null;
  onRoute: (patch: Partial<Route>) => void;
}

export function TopBar({ route, version, versions, slices, onRoute }: Props) {
  const verdict: Verdict = route.verdict ?? "texture";
  const counts = STATUSES.map(status => ({
    status,
    n: slices ? slices.filter(s => s[verdict].verdict === status).length : 0,
  }));

  return (
    <header className="topbar">
      <select
        aria-label="Version"
        value={version}
        onChange={e => onRoute({ version: e.target.value })}
      >
        {versions.map(v => (
          <option key={v.name} value={v.name}>{v.name}</option>
        ))}
      </select>

      <div className="segmented" role="group" aria-label="Verdict">
        {VERDICTS.map(item => (
          <button
            key={item.verdict}
            type="button"
            aria-pressed={verdict === item.verdict}
            onClick={() => onRoute({ verdict: item.verdict })}
          >
            {item.label}
          </button>
        ))}
      </div>

      <nav>
        {VIEW_LINKS.map(item => (
          <a
            key={item.view}
            href={toHash({ view: item.view, version, verdict })}
            aria-current={route.view === item.view ? "page" : undefined}
          >
            {item.label}
          </a>
        ))}
      </nav>

      <div className="pills">
        {counts.map(({ status, n }) => (
          <span key={status} className="pill" style={{ borderColor: COLOR[status] }}>
            {status} {n}
          </span>
        ))}
      </div>
    </header>
  );
}
