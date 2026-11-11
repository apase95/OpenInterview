import s from "./workspace.module.css";
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <p className={s.notice} role="alert">
      {error}
    </p>
  ) : null;
}
export const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Could not connect. Please try again.";
