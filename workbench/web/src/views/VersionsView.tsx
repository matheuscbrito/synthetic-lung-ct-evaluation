import { useState, type FormEvent } from "react";
import { ApiError, del, post, type Version } from "../api";

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

export function VersionsView({ versions, onChanged, onRecalculate }: Props) {
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [adding, setAdding] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [rowError, setRowError] = useState<{ name: string; text: string } | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAdding(true);
    setFormError(null);
    try {
      await post("/api/versions", { name: name.trim(), folder: folder.trim() });
      setName("");
      setFolder("");
      await onChanged();
    } catch (e) {
      setFormError(message(e));
    } finally {
      setAdding(false);
    }
  };

  const remove = async (version: string) => {
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
    <div className="versions">
      <div className="versions-head">
        <button type="button" onClick={recalculate} disabled={recalculating}>
          {recalculating ? "Recalculating…" : "Recalculate"}
        </button>
        {recalcError && <span className="tool-error">{recalcError}</span>}
      </div>

      <div className="table-wrap">
        <table className="versions-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Mode</th>
              <th>Slices</th>
              <th>Added</th>
              <th>Folder</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {versions.map(v => (
              <tr key={v.name}>
                <td>{v.name}</td>
                <td>{v.mode}</td>
                <td className="num">{v.n_cases}</td>
                <td>{v.added}</td>
                <td className="folder">{v.folder}</td>
                <td>
                  {v.is_baseline ? (
                    <span className="muted">baseline</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => remove(v.name)}
                      disabled={removing !== null}
                    >
                      {removing === v.name ? "Removing…" : "Remove"}
                    </button>
                  )}
                  {rowError?.name === v.name && <div className="tool-error">{rowError.text}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form className="versions-form" onSubmit={add}>
        <input
          aria-label="Version name"
          placeholder="Name"
          value={name}
          onChange={e => setName(e.target.value)}
          required
          disabled={adding}
        />
        <input
          aria-label="Folder"
          placeholder="Folder path"
          value={folder}
          onChange={e => setFolder(e.target.value)}
          required
          disabled={adding}
        />
        <button type="submit" disabled={adding}>
          {adding ? "Evaluating…" : "Add version"}
        </button>
        {formError && <span className="tool-error">{formError}</span>}
      </form>
    </div>
  );
}
