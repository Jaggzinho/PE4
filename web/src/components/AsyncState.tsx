import { ApiError, errorMessage } from "../api/client";


export function LoadingNotice({ children = "Loading…" }: { children?: string }) {
  return <div className="muted" aria-live="polite">{children}</div>;
}


export function EmptyNotice({ children }: { children: string }) {
  return <div className="muted">{children}</div>;
}


export function ErrorNotice({ error }: { error: unknown }) {
  const permissionDenied = error instanceof ApiError && error.status === 403;
  return (
    <div className="card" role="alert" style={{ color: "var(--danger)", marginBottom: 12 }}>
      {permissionDenied ? "You do not have permission to view or change this data." : errorMessage(error)}
    </div>
  );
}
