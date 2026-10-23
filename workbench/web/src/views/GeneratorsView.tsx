import { useEffect, useState } from "react";
import { ApiError, get, type Board, type Slice, type SlicesResponse } from "../api";
import type { Route } from "../route";
import { GeneratorBoard, MetricDistribution } from "../components/GeneratorBoard";
import { ManyGenerators } from "../components/ManyGenerators";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

// Cache de módulo por versão: a lista de cortes de cada versão é buscada uma única vez.
const pending = new Map<string, Promise<Slice[]>>();

function slicesOf(version: string): Promise<Slice[]> {
  const hit = pending.get(version);
  if (hit) return hit;
  const request = get<SlicesResponse>("/api/slices", { version }).then(
    r => r.slices,
    error => {
      pending.delete(version);
      throw error;
    },
  );
  pending.set(version, request);
  return request;
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
          if (live) setSlicesByVersion(prev => (prev[gen.name] ? prev : { ...prev, [gen.name]: slices }));
        })
        .catch(e => live && setError(message(e)));
    }
    return () => {
      live = false;
    };
  }, [board]);

  if (error) return <div className="error">{error}</div>;
  if (!board) return null;

  return (
    <div className="generators">
      <GeneratorBoard board={board} onRoute={onRoute} />
      {board.generators.length > 1 && (
        <>
          <MetricDistribution generators={board.generators} slicesByVersion={slicesByVersion} />
          <ManyGenerators
            generators={board.generators}
            slicesByVersion={slicesByVersion}
            verdict={route.verdict ?? "texture"}
          />
        </>
      )}
    </div>
  );
}
