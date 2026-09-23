import { AnalysisHistory } from "@/components/resume-selector/history";
import { ResumeSelector } from "@/components/resume-selector/resume-selector";

export default function ClientResumeSelectorPage() {
  return (
    <div>
      <ResumeSelector />
      <AnalysisHistory />
    </div>
  );
}
