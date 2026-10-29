import { useEffect, useMemo, useState } from "react";
import {
  mdListComponentTypes,
  mdListComponents,
  mdListContacts,
  mdListMaterials,
  mdListProperties,
  mdListTolerances,
  mdListTemplates,
  type Component,
  type ComponentType,
  type Contact,
  type EmailTemplate,
  type Material,
  type Property,
  type Tolerance,
} from "../api";

import {
  ComponentTypesTab,
  ComponentsTab,
  ContactsTab,
  MaterialsTab,
  PropertiesTab,
  TemplatesTab,
  TolerancesTab,
} from "../features/masterData";
import { ErrorNotice, LoadingNotice } from "../components/AsyncState";

type Tab = "materials" | "contacts" | "templates" | "component_types" | "components" | "properties" | "tolerances";

export default function MasterDataPage() {
  const [tab, setTab] = useState<Tab>("materials");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadedTab, setLoadedTab] = useState<Tab | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const [materials, setMaterials] = useState<Material[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [types, setTypes] = useState<ComponentType[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [tolerances, setTolerances] = useState<Tolerance[]>([]);

  async function refresh() {
    setErr(null);
    if (tab === "materials") setMaterials(await mdListMaterials());
    if (tab === "contacts") setContacts(await mdListContacts());
    if (tab === "templates") setTemplates(await mdListTemplates());
    if (tab === "component_types") setTypes(await mdListComponentTypes());
    if (tab === "components") {
      const [ts, cs] = await Promise.all([mdListComponentTypes(), mdListComponents()]);
      setTypes(ts);
      setComponents(cs);
    }
    if (tab === "properties") setProperties(await mdListProperties());
    if (tab === "tolerances") {
      const [mats, props, tols] = await Promise.all([mdListMaterials(), mdListProperties(), mdListTolerances()]);
      setMaterials(mats);
      setProperties(props);
      setTolerances(tols);
    }
    setLoadedTab(tab);
  }

  useEffect(() => {
    setLoading(true);
    refresh().catch(setErr).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function doWork(fn: () => Promise<void>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  const typeOptions = useMemo(() => types.slice().sort((a, b) => a.name.localeCompare(b.name)), [types]);
  const unavailable = busy || loading;

  return (
    <div className="card">
      <h2 className="title">Master Data</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn" onClick={() => setTab("materials")} disabled={unavailable || tab === "materials"}>
          Materials
        </button>
        <button className="btn" onClick={() => setTab("contacts")} disabled={unavailable || tab === "contacts"}>
          Contacts
        </button>
        <button className="btn" onClick={() => setTab("templates")} disabled={unavailable || tab === "templates"}>
          Email Templates
        </button>
        <button className="btn" onClick={() => setTab("component_types")} disabled={unavailable || tab === "component_types"}>
          Component Types
        </button>
        <button className="btn" onClick={() => setTab("components")} disabled={unavailable || tab === "components"}>
          Components
        </button>
        <button className="btn" onClick={() => setTab("properties")} disabled={unavailable || tab === "properties"}>
          Properties
        </button>
        <button className="btn" onClick={() => setTab("tolerances")} disabled={unavailable || tab === "tolerances"}>
          Tolerances
        </button>
        <div className="spacer" />
        <button className="btn" onClick={() => { setLoading(true); refresh().catch(setErr).finally(() => setLoading(false)); }} disabled={unavailable}>
          Refresh
        </button>
      </div>

      {err != null && <ErrorNotice error={err} />}
      {loading && <LoadingNotice>Loading master data…</LoadingNotice>}
      {busy && <div role="status" className="muted">Saving changes…</div>}

      {!loading && loadedTab === tab && tab === "materials" && (
        <MaterialsTab busy={busy} rows={materials} onWork={doWork} />
      )}
      {!loading && loadedTab === tab && tab === "contacts" && (
        <ContactsTab busy={busy} rows={contacts} onWork={doWork} />
      )}
      {!loading && loadedTab === tab && tab === "templates" && (
        <TemplatesTab busy={busy} rows={templates} onWork={doWork} />
      )}
      {!loading && loadedTab === tab && tab === "component_types" && (
        <ComponentTypesTab busy={busy} rows={types} onWork={doWork} />
      )}
      {!loading && loadedTab === tab && tab === "components" && (
        <ComponentsTab busy={busy} rows={components} types={typeOptions} onWork={doWork} />
      )}
      {!loading && loadedTab === tab && tab === "properties" && <PropertiesTab busy={busy} rows={properties} onWork={doWork} />}
      {!loading && loadedTab === tab && tab === "tolerances" && <TolerancesTab busy={busy} rows={tolerances} materials={materials} properties={properties} onWork={doWork} />}
    </div>
  );
}
