import { redirect } from "next/navigation";

/**
 * Root redirect. All authenticated users land on /cases as the primary view.
 */
export default function HomePage() {
  redirect("/metrics");
}
