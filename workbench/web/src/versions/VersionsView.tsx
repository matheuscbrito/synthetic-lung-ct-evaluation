// Dataset-independent history screen (mockups v3, slide "Versions"): versions, detected runs and add form.
// Everything comes from the contract. Writes clear the contract cache and remount the lists (`rev`),
// so every read is refetched; a late response after a dataset switch never reaches the new screen.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { del, patch, post } from "../api";
import { clearContractCache, useContract } from "../contract/client";
import type { DetectedRun, Schema, VersionInfo } from "../contract/types";
import type { Route } from "../route";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import { Seg } from "../ui/Seg";
import "./versions.css";

const enc = encodeURIComponent;
// same rule as the API (`^[A-Za-z0-9 #._-]{1,40}$`); the server stays the authority
const LABEL_PATTERN = "[A-Za-z0-9 #._-]{1,40}";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface RunRef {
  key: string;
  label: string;
}

interface NewVersion {
  message: string;
  name: string;
}

export interface AddBody {
  name?: string;
  folder: string;
  label?: string;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Short date as in the deck ("16 Oct"), read from the ISO text so the time zone never shifts it.
export function shortDate(iso: string): string {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(iso);
  const month = m ? MONTHS[Number(m[1]) - 1] : undefined;
  return m && month ? `${Number(m[2])} ${month}` : iso;
}

// Summary line: mode · n items · n common pairs · warnings · from <run> #<step>.
export function versionSummary(v: VersionInfo, item: string, runLabel: Map<string, string>): string {
  const parts = [v.mode_label, `${v.n_items} ${item}`, `${v.n_common} common pairs`];
  for (const w of v.warnings) parts.push(`${w.count} ${w.label}`);
  if (v.provenance) parts.push(`from ${runLabel.get(v.provenance.run) ?? v.provenance.run} #${v.provenance.step}`);
  return parts.join(" · ");
}

interface Props {
  schema: Schema;
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  onChanged: () => void;
}

export function VersionsView({ schema, route, onRoute, onChanged }: Props) {
  const dataset = schema.dataset.key;
  const item = schema.dataset.item.plural;
  const [rev, setRev] = useState(0);
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [id, setId] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const busy = pending !== null || recalculating;

  // write finished: contract cache cleared, lists refetched, dataset status reloaded by the parent
  const wrote = () => {
    clearContractCache();
    setRev(n => n + 1);
    onChanged();
  };

  const add = async (body: AddBody): Promise<boolean> => {
    setPending(body.label ?? body.name ?? "New version");
    setFormError(null);
    setNotice(null);
    try {
      const done = await post<NewVersion>(`/api/versions?dataset=${enc(dataset)}`, body);
      wrote();
      if (alive.current) {
        onRoute({ version: done.name });
        setNotice(done.message);
      }
      return true;
    } catch (e) {
      if (alive.current) setFormError(message(e));
      return false;
    } finally {
      if (alive.current) setPending(null);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const done = await add({
      name: name.trim() || undefined,
      folder: folder.trim(),
      label: id.trim() || undefined,
    });
    if (done && alive.current) {
      setName("");
      setFolder("");
      setId("");
    }
  };

  const recalculate = async () => {
    setRecalculating(true);
    setRecalcError(null);
    try {
      await post(`/api/refresh?dataset=${enc(dataset)}`);
      wrote();
    } catch (e) {
      if (alive.current) setRecalcError(message(e));
    } finally {
      if (alive.current) setRecalculating(false);
    }
  };

  return (
    <div className="versions-view">
      <PageHeader
        eyebrow={`History · ${schema.dataset.mode_label}`}
        title="Versions"
        sub="Each version is measured once with the frozen ruler"
        right={
          <>
            {schema.datasets.length > 1 && (
              <div className="dsw">
                <Seg<string>
                  small
                  label="Dataset"
                  value={dataset}
                  onChange={key => onRoute({ dataset: key, version: undefined })}
                  options={schema.datasets.map(d => ({ value: d.key, label: d.label }))}
                />
              </div>
            )}
            {recalcError && <span className="tool-error">{recalcError}</span>}
            <button type="button" className="dark" onClick={recalculate} disabled={busy}>
              {recalculating ? "Recalculating…" : "Recalculate"}
            </button>
          </>
        }
      />

      <div className="vgrid">
        <div className="vleft">
          <VersionLists
            key={rev}
            dataset={dataset}
            item={item}
            selected={route.version}
            pending={pending}
            busy={busy}
            onWrite={wrote}
            onAdd={add}
          />
        </div>

        <Card>
          <div className="eyebrow ink">Add version</div>
          <form onSubmit={submit}>
            <label className="field">
              <span className="sub">
                Name <i>(optional)</i>
              </span>
              <input
                className="inp mono"
                aria-label="Version name"
                placeholder="Version name"
                value={name}
                onChange={e => setName(e.target.value)}
                disabled={busy}
              />
            </label>
            <label className="field">
              <span className="sub">Folder</span>
              <input
                className="inp mono"
                aria-label="Folder"
                placeholder="/path/to/version/folder"
                value={folder}
                onChange={e => setFolder(e.target.value)}
                required
                disabled={busy}
              />
            </label>
            <label className="field">
              <span className="sub">
                Id <i>(optional)</i>
              </span>
              <input
                className="inp mono"
                aria-label="Version id"
                placeholder="Shown in the workbench"
                value={id}
                maxLength={40}
                pattern={LABEL_PATTERN}
                onChange={e => setId(e.target.value)}
                disabled={busy}
              />
            </label>
            <div className="add-foot">
              <button type="submit" className="dark" disabled={busy}>
                {pending !== null ? "Adding…" : "Add and evaluate"}
              </button>
              {formError && <span className="tool-error">{formError}</span>}
              {notice && (
                <span className="sub" role="status">
                  {notice}
                </span>
              )}
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}

interface ListsProps {
  dataset: string;
  item: string;
  selected: string | undefined;
  pending: string | null;
  busy: boolean;
  onWrite: () => void;
  onAdd: (body: AddBody) => Promise<boolean>;
}

// Reads the versions, the detected runs and the run labels; remounted after each write.
function VersionLists({ dataset, item, selected, pending, busy, onWrite, onAdd }: ListsProps) {
  const params = { dataset };
  const versions = useContract<VersionInfo[]>("/api/v2/versions", params);
  const detected = useContract<DetectedRun[]>("/api/versions/detected", params);
  // run labels are cosmetic: without them the raw run key is shown
  const runs = useContract<{ runs: RunRef[] }>("/api/runs", {});
  const runLabel = new Map((runs.data?.runs ?? []).map(r => [r.key, r.label]));
  const list = versions.data;
  const found = detected.data;

  return (
    <>
      <Card>
        <div className="eyebrow ink">{list ? `Versions · ${list.length}` : "Versions"}</div>
        {versions.error && <div className="tool-error">{versions.error}</div>}
        {!list && !versions.error && <div className="sub">Loading versions…</div>}
        {list && (
          <div role="list" aria-label="Versions">
            {list.map(v => (
              <VersionRow
                key={v.name}
                v={v}
                summary={versionSummary(v, item, runLabel)}
                selected={selected === v.name}
                dataset={dataset}
                busy={busy}
                onWrite={onWrite}
              />
            ))}
          </div>
        )}
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
      </Card>

      <Card>
        <div className="eyebrow ink">{found ? `Detected runs · ${found.length}` : "Detected runs"}</div>
        {detected.error && <div className="tool-error">{detected.error}</div>}
        {found && found.length === 0 && (
          <div className="empty">
            <div className="eb" aria-hidden="true">
              ◌
            </div>
            <b>No runs detected</b>
            <div className="sub">
              Completed runs found in the configured run folders appear here, ready to add as a version.
            </div>
          </div>
        )}
        {found && found.length > 0 && (
          <div role="list" aria-label="Detected runs">
            {found.map(d => (
              <div className="vrow" role="listitem" key={`${d.name}|${d.folder}`}>
                <div>
                  <b>{d.name}</b>
                  <div className="sub mono">{d.folder}</div>
                </div>
                <button
                  type="button"
                  className="dark sm"
                  disabled={busy}
                  onClick={() => void onAdd({ name: d.name, folder: d.folder })}
                >
                  Add
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

interface RowProps {
  v: VersionInfo;
  summary: string;
  selected: boolean;
  dataset: string;
  busy: boolean;
  onWrite: () => void;
}

// One version: label, summary, date, Remove (not for the reference) and inline Edit id.
function VersionRow({ v, summary, selected, dataset, busy, onWrite }: RowProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(v.label);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const url = `/api/versions/${enc(v.name)}?dataset=${enc(dataset)}`;

  const startEdit = () => {
    setDraft(v.label);
    setError(null);
    setEditing(true);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await patch(url, { label: draft.trim() });
      setEditing(false);
      onWrite();
    } catch (e) {
      setError(message(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Remove version ${v.label}?`)) return;
    setRemoving(true);
    setError(null);
    try {
      await del(url);
      onWrite();
    } catch (e) {
      setError(message(e));
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className="vrow-block" role="listitem" aria-current={selected || undefined}>
      <div className="vrow">
        <div>
          <b>{v.label}</b>
          <div className="sub">{summary}</div>
          {editing ? (
            <form className="vrow-edit" onSubmit={save}>
              <input
                className="inp mono"
                aria-label={`Id for ${v.label}`}
                value={draft}
                maxLength={40}
                pattern={LABEL_PATTERN}
                required
                disabled={saving}
                onChange={e => setDraft(e.target.value)}
              />
              <button type="submit" className="dark sm" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
              <button type="button" className="ghost" disabled={saving} onClick={() => setEditing(false)}>
                Cancel
              </button>
            </form>
          ) : (
            <button type="button" className="ghost" disabled={busy || removing} onClick={startEdit}>
              Edit id
            </button>
          )}
        </div>
        <span className="mono sub">{shortDate(v.added)}</span>
        {v.is_reference ? (
          <span />
        ) : (
          <button type="button" className="ghost" disabled={busy || removing} onClick={remove}>
            {removing ? "Removing…" : "Remove"}
          </button>
        )}
        {v.is_reference ? <span className="pill base">ruler reference</span> : <span className="okc" aria-label="evaluated">✓</span>}
      </div>
      {error && <div className="tool-error">{error}</div>}
    </div>
  );
}
