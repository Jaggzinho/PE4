import { useState } from "react";
import { settingsCreateOutlookTestDraft, settingsDownloadOutlookTestEml } from "../../api/settings";
import { errorMessage } from "../../api/client";

export function OutlookTab() {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await action();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="outlook-title">
      <h3 id="outlook-title">Outlook test draft</h3>
      <p className="muted">Creates a recipient-free test message in Classic Outlook. It is saved to Drafts and opened for review; nothing is sent.</p>
      <div className="row">
        <button className="btn" disabled={busy} onClick={() => run(async () => {
          const result = await settingsCreateOutlookTestDraft();
          setNotice(result.message);
        })}>Create test draft in Outlook</button>
        <button className="btn" disabled={busy} onClick={() => run(async () => {
          const blob = await settingsDownloadOutlookTestEml();
          const url = URL.createObjectURL(blob);
          try {
            const link = document.createElement("a");
            link.href = url;
            link.download = "pe3-outlook-test.eml";
            document.body.appendChild(link);
            link.click();
            link.remove();
          } finally {
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }
          setNotice("Test .eml draft downloaded. Open it in your mail client to review it.");
        })}>Download .eml instead</button>
      </div>
      {busy && <p role="status">Preparing draft…</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error} You can still download the .eml draft.</p>}
    </section>
  );
}
