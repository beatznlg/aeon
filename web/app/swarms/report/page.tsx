"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SwarmReportIndex() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to the main swarms page if no ID is provided
    router.replace("/swarms");
  }, [router]);

  return (
    <div className="report-page">
      <div className="report-loading">
        <div className="report-spinner" />
        <p>Redirecting to swarms page...</p>
      </div>
    </div>
  );
}
