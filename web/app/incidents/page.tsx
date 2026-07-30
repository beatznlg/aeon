import { guardModuleRoute } from "@/lib/module-guard";
import IncidentsPageClient from "./IncidentsPageClient";

export default async function IncidentsPage() {
  await guardModuleRoute("incidents", "/os");
  return <IncidentsPageClient />;
}
