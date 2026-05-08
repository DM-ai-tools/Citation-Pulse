import { Button } from "./Button";

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-red-100 bg-red-50/80 p-8 text-center">
      <p className="font-semibold text-red-900">{title}</p>
      {message && <p className="mt-2 text-sm text-red-800">{message}</p>}
      {onRetry && (
        <Button variant="secondary" className="mt-4" type="button" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
