import { guardModuleRoute } from "@/lib/module-guard";
import AnomaliesPageClient from "./AnomaliesPageClient";

export default async function AnomaliesPage() {
  await guardModuleRoute("anomalies", "/os");
  return <AnomaliesPageClient />;
}
