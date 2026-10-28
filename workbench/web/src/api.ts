// Transporte HTTP do workbench: GET/POST/DELETE/PATCH com erro tipado e a URL das imagens.
// As formas das respostas do contrato ficam em contract/types.ts.

// Resposta de GET /api/status (estado do histórico do dataset).
export interface ServerStatus {
  stale: boolean;
  has_history: boolean;
  baseline: string | null;
  token: number | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | undefined>;

function query(params?: Params): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(method: string, path: string, params?: Params, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${path}${query(params)}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {
      // corpo que não é JSON: fica com o texto de status
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function get<T>(path: string, params?: Params): Promise<T> {
  return request<T>("GET", path, params);
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, undefined, body);
}

export function del<T>(path: string): Promise<T> {
  return request<T>("DELETE", path);
}

export function patch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PATCH", path, undefined, body);
}

const enc = encodeURIComponent;

// Token do histórico (mtime de historico.json): muda quando o histórico muda e invalida o cache do navegador.
let imageToken: number | null = null;

export function setImageToken(token: number | null): void {
  imageToken = token;
}

// reference: janela de intensidade da real do corte, igual em todas as versões (comparações lado a lado).
// dataset: omitido usa o dataset padrão do backend.
export function imageUrl(
  version: string,
  caseId: string,
  kind: "real" | "synthetic" | "diff" | "contour",
  size?: number,
  reference = false,
  dataset?: string,
): string {
  const params: Params = { size: size || undefined, window: reference ? "reference" : undefined, dataset };
  if (imageToken !== null) params.v = imageToken;
  return `/api/image/${enc(version)}/${enc(caseId)}/${kind}.png${query(params)}`;
}
