import { SheetConfigList } from "@/components/sheet-config/sheet-config-row";

export default function ClientConfigPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Config</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Pick the Google Sheet each resume type&apos;s analyses are recorded to.
      </p>
      <div className="mt-6">
        <SheetConfigList />
      </div>
    </div>
  );
}
