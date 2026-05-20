import { redirect } from "next/navigation";

/** Send visitors to login; authenticated users reach /landing via the login flow or bookmark. */
export default function HomePage() {
  redirect("/login");
}
