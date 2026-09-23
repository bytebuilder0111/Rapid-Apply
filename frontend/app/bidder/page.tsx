import { AnalysisHistory } from "@/components/resume-selector/history";
import { ResumeSelector } from "@/components/resume-selector/resume-selector";

export default function BidderResumeSelectorPage() {
  return (
    <div>
      <ResumeSelector />
      <AnalysisHistory />
    </div>
  );
}
