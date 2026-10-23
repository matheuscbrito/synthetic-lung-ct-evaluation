import { useEffect, useState } from "react";
import { ApiError, get, type Board, type Slice, type Verdict } from "../api";
import type { Route } from "../route";
import { GeneratorBoard, MetricDistribution } from "../components/GeneratorBoard";
import { ManyGenerators } from "../components/ManyGenerators";
import { bestTexture } from "../components/boardRows";
import { slicesOf } from "../slices";
import { PageHeader } from "../ui/PageHeader";
import { Kpi } from "../ui/Kpi";
import { Card } from "../ui/Card";
import { Seg } from "../ui/Seg";

const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
];

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export function GeneratorsView({ route, onRoute }: Props) {
  const [board, setBoard] = useState<Board | null>(null);
  const [slicesByVersion, setSlicesByVersion] = useState<Record<string, Slice[]>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    get<Board>("/api/board")
      .then(next => {
        if (live) setBoard(next);
      })
      .catch(e => live && setError(message(e)));
    return () => {
      live = false;
    };
  }, []);

  // Só com mais de uma versão há cortes para comparar; a referência sozinha mostra apenas o placar.
  useEffect(() => {
    if (!board || board.generators.length < 2) return;
    let live = true;
    for (const gen of board.generators) {
      slicesOf(gen.name)
        .then(slices => {
          if (live) setSlicesByVersion(prev => ({ ...prev, [gen.name]: slices }));
        })
        .catch(e => live && setError(message(e)));
    }
    return () => {
      live = false;
    };
  }, [board]);

  if (error) return <div className="error">{error}</div>;
  if (!board) return null;

  const candidates = board.generators.filter(g => !g.is_baseline).length;
  const best = bestTexture(board.generators);
  const baseline = board.generators.find(g => g.is_baseline);
  const baselineApproved = baseline?.counts.texture.approved ?? 0;

  return (
    <div className="gen-view">
      <PageHeader
        eyebrow="GENERATORS · VS BASELINE"
        title="Benchmark"
        sub={`Same ${board.n_cases} slices · same frozen ruler`}
        right={
          candidates > 0 && (
            <span className="tag">{candidates === 1 ? "1 candidate" : `${candidates} candidates`}</span>
          )
        }
      />

      <div className="kcards">
        {best ? (
          <div className="kcard">
            <Kpi label="Best texture approval" value={best.approved} suffix={best.name} countUp />
          </div>
        ) : (
          <div className="kcard">
            <Kpi label={`Baseline ${board.baseline}`} value={baselineApproved} suffix={`of ${board.n_cases}`} countUp />
          </div>
        )}
        {best && (
          <div className="kcard">
            <Kpi label={`Baseline ${board.baseline}`} value={baselineApproved} suffix={`of ${board.n_cases}`} countUp />
          </div>
        )}
      </div>

      <GeneratorBoard board={board} onRoute={onRoute} />

      {board.generators.length > 1 && (
        <>
          <Card>
            <div className="eyebrow">Metric distribution</div>
            <MetricDistribution generators={board.generators} slicesByVersion={slicesByVersion} />
          </Card>
          <Card>
            <div className="gen-card-head">
              <div className="eyebrow">Many generators</div>
              <Seg<Verdict>
                label="Verdict"
                options={VERDICT_OPTIONS}
                value={route.verdict ?? "texture"}
                onChange={v => onRoute({ verdict: v })}
                small
              />
            </div>
            <ManyGenerators
              generators={board.generators}
              slicesByVersion={slicesByVersion}
              verdict={route.verdict ?? "texture"}
            />
          </Card>
        </>
      )}
    </div>
  );
}
