import { redirect } from "next/navigation";

const bypass =
  process.env.AUTH_DISABLE_JWT === "true" ||
  process.env.NEXT_PUBLIC_AUTH_DISABLE_JWT === "true" ||
  process.env.NEXT_PUBLIC_AUTH_BYPASS === "true";

export default function HomePage() {
  redirect(bypass ? "/landing" : "/login");
}
