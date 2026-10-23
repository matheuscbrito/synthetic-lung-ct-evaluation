import { useState, type FormEvent } from "react";
import { ApiError, del, post, type Version } from "../api";
import { PageHeader } from "../ui/PageHeader";
import { Card } from "../ui/Card";

interface Props {
  versions: Version[];
  // recarrega versões e cortes depois de uma mudança no histórico
  onChanged: () => Promise<void>;
  // recalcula o histórico (o mesmo caminho do botão da tela de estado obsoleto)
  onRecalculate: () => Promise<void>;
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

// Data de adição em texto curto, como no deck ("16 Oct"); valor desconhecido segue como veio.
function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function VersionsView({ versions, onChanged, onRecalculate }: Props) {
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [rowError, setRowError] = useState<{ name: string; text: string } | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  const busy = pending !== null || removing !== null || recalculating;

  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next = name.trim();
    setPending(next);
    setFormError(null);
    try {
      await post("/api/versions", { name: next, folder: folder.trim() });
      setName("");
      setFolder("");
      await onChanged();
    } catch (e) {
      setFormError(message(e));
    } finally {
      setPending(null);
    }
  };

  const remove = async (version: string) => {
    if (!window.confirm(`Remove version ${version}?`)) return;
    setRemoving(version);
    setRowError(null);
    try {
      await del(`/api/versions/${encodeURIComponent(version)}`);
      await onChanged();
    } catch (e) {
      setRowError({ name: version, text: message(e) });
    } finally {
      setRemoving(null);
    }
  };

  const recalculate = async () => {
    setRecalculating(true);
    setRecalcError(null);
    try {
      await onRecalculate();
    } catch (e) {
      setRecalcError(message(e));
    } finally {
      setRecalculating(false);
    }
  };

  return (
    <div className="versions-view">
      <PageHeader
        eyebrow="History · outputs/placar"
        title="Versions"
        sub="Each version is measured once with the frozen ruler"
        right={
          <>
            {recalcError && <span className="tool-error">{recalcError}</span>}
            <button type="button" className="dark" onClick={recalculate} disabled={busy}>
              {recalculating ? "Recalculating…" : "Recalculate"}
            </button>
          </>
        }
      />

      <div className="vgrid">
        <Card>
          {versions.map(v => (
            <div key={v.name} className="vrow-block">
              <div className="vrow">
                <div>
                  <b>{v.name}</b>
                  <div className="sub">{`${v.mode} · ${v.n_cases} slices`}</div>
                </div>
                <span className="mono sub">{shortDate(v.added)}</span>
                {v.is_baseline ? (
                  <>
                    <span className="pill base">baseline</span>
                    <span />
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => remove(v.name)}
                      disabled={busy}
                    >
                      {removing === v.name ? "Removing…" : "Remove"}
                    </button>
                    <span className="okc" aria-label="evaluated">✓</span>
                  </>
                )}
              </div>
              {rowError?.name === v.name && <div className="tool-error">{rowError.text}</div>}
            </div>
          ))}

          {pending !== null && (
            <div className="vrow vrow-pending" role="status">
              <div>
                <b>{pending}</b>
                <div className="sub">Evaluating…</div>
              </div>
              <span className="mono sub">now</span>
              <span />
              <span className="spin" aria-hidden="true" />
            </div>
          )}

          <div className="cfoot sub">
            {`${versions.length} evaluated`}
            {pending !== null && " · 1 evaluating"}
          </div>
        </Card>

        <Card>
          <div className="eyebrow ink">Add version</div>
          <form onSubmit={add}>
            <label className="field">
              <span className="sub">Name</span>
              <input
                className="inp mono"
                aria-label="Version name"
                placeholder="Name"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                disabled={pending !== null}
              />
            </label>
            <label className="field">
              <span className="sub">Folder</span>
              <input
                className="inp mono"
                aria-label="Folder"
                placeholder="Folder path"
                value={folder}
                onChange={e => setFolder(e.target.value)}
                required
                disabled={pending !== null}
              />
            </label>
            <div className="add-foot">
              <button type="submit" className="dark" disabled={busy}>
                Add version
              </button>
              {formError && <span className="tool-error">{formError}</span>}
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
