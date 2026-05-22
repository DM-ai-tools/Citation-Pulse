import { redirect } from "next/navigation";

/**
 * Dashboard workspace UI is disabled — gaps-only navigation in production.
 * Full dashboard implementation is preserved in git history (pre–gaps-only change).
 */
export default function DashboardPage() {
  redirect("/dashboard/gaps");
}
