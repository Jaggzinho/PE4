import { useSearchParams } from "react-router-dom";
import ImportPage from "./ImportPage";
import MasterDataPage from "./MasterDataPage";
import SettingsPage from "./SettingsPage";

type Section = "import" | "master-data" | "application";

type Props = {
  canEditMaster: boolean;
  canManageUsers: boolean;
};

const sections: Array<{ id: Section; label: string }> = [
  { id: "import", label: "Import" },
  { id: "master-data", label: "Master Data" },
  { id: "application", label: "Application settings" },
];

function isSection(value: string | null): value is Section {
  return sections.some((section) => section.id === value);
}

export default function SettingsHubPage({ canEditMaster, canManageUsers }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSection = searchParams.get("section");
  const section: Section = isSection(requestedSection) ? requestedSection : "import";

  const visibleSections = sections.filter(({ id }) => {
    if (id === "master-data") return canEditMaster;
    if (id === "application") return canManageUsers;
    return true;
  });

  function selectSection(nextSection: Section) {
    setSearchParams({ section: nextSection });
  }

  return (
    <div className="settings-hub">
      <div className="card settings-hub-header">
        <h2 className="title">Settings</h2>
        <div className="row" role="tablist" aria-label="Settings sections">
          {visibleSections.map(({ id, label }) => (
            <button
              key={id}
              className={`btn${section === id ? " primary" : ""}`}
              type="button"
              role="tab"
              aria-selected={section === id}
              onClick={() => selectSection(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div role="tabpanel">
        {section === "import" && <ImportPage />}
        {section === "master-data" &&
          (canEditMaster ? (
            <MasterDataPage />
          ) : (
            <div className="card" role="alert">You do not have permission to view Master Data.</div>
          ))}
        {section === "application" &&
          (canManageUsers ? (
            <SettingsPage />
          ) : (
            <div className="card" role="alert">You do not have permission to view Application settings.</div>
          ))}
      </div>
    </div>
  );
}
