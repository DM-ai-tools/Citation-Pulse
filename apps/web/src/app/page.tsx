import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const jar = await cookies();
  const token = jar.get("cp_token")?.value;
  redirect(token ? "/landing" : "/login");
}
