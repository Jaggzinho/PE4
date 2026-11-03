import { useId, useRef, useState, type KeyboardEvent } from "react";
import type { Environment } from "../api/auth";
import EnvironmentLabel from "./EnvironmentLabel";

export default function EnvironmentSelect({ environments, value, onChange, disabled }: {
  environments: Environment[]; value: string; onChange: (id: string) => void; disabled: boolean;
}) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const selected = environments.find((item) => item.environment_id === value);

  function choose(index: number) {
    const item = environments[index];
    if (item?.available) {
      onChange(item.environment_id);
      setOpen(false);
      button.current?.focus();
    }
  }

  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      setOpen(true);
      setActive((index) => event.key === "Home" ? 0 : event.key === "End" ? environments.length - 1
        : Math.max(0, Math.min(environments.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
    } else if ((event.key === "Enter" || event.key === " ") && open) {
      event.preventDefault();
      choose(active);
    } else if (event.key === "Escape" || event.key === "Tab") {
      setOpen(false);
    }
  }

  return <div style={{ position: "relative" }} onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  }}>
    <label id={`${id}-label`} htmlFor={id}>Environment</label>
    <button ref={button} id={id} className="input" type="button" role="combobox"
      aria-labelledby={`${id}-label`} aria-expanded={open} aria-controls={`${id}-options`}
      aria-haspopup="listbox" aria-activedescendant={open ? `${id}-option-${active}` : undefined}
      disabled={disabled} onKeyDown={keyDown} onClick={() => {
        setActive(Math.max(0, environments.findIndex((item) => item.environment_id === value)));
        setOpen(!open);
      }} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", marginTop: 4 }}>
      {selected ? <EnvironmentLabel environment={selected} /> : "Select an environment"}<span aria-hidden="true">▾</span>
    </button>
    {open && <div id={`${id}-options`} role="listbox" aria-labelledby={`${id}-label`}
      className="card" style={{ position: "absolute", zIndex: 20, width: "100%", padding: 4, boxSizing: "border-box",
        background: "var(--panel)", boxShadow: "0 8px 24px rgba(0,0,0,0.25)" }}>
      {environments.map((item, index) => <div key={item.environment_id} id={`${id}-option-${index}`}
        role="option" aria-selected={item.environment_id === value} aria-disabled={!item.available}
        onMouseDown={(event) => event.preventDefault()} onMouseMove={() => setActive(index)} onClick={() => choose(index)}
        style={{ padding: "10px 8px", cursor: item.available ? "pointer" : "default", opacity: item.available ? 1 : 0.55,
          outline: index === active ? "2px solid var(--accent, #2563eb)" : undefined, borderRadius: 4 }}>
        <EnvironmentLabel environment={item} />{!item.available && " (Unavailable)"}
      </div>)}
    </div>}
  </div>;
}
