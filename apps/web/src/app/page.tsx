import { redirect } from "next/navigation";
import { isAuthBypass } from "@/lib/authBypass";

export default function HomePage() {
  redirect(isAuthBypass() ? "/landing" : "/login");
}
