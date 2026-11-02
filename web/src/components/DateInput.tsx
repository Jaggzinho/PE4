import { useEffect, useId, useRef, useState, type InputHTMLAttributes } from "react";
import { CalendarDays } from "lucide-react";
import { formatDate, parseDisplayDate } from "../dateFormat";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange" | "min" | "max"> & {
  value: string;
  onValueChange: (iso: string) => void;
  min?: string;
  max?: string;
};

export function DateInput({ value, onValueChange, min, max, ...props }: Props) {
  const [text, setText] = useState(() => formatDate(value, ""));
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const errorId = useId();
  useEffect(() => {
    setText(formatDate(value, ""));
    setError("");
    input.current?.setCustomValidity("");
  }, [value]);

  return <span style={{ display: "inline-flex", flexDirection: "column" }}>
    <span style={{ display: "inline-flex", alignItems: "center", position: "relative" }}>
    <input {...props} ref={input} type="text" inputMode="numeric" placeholder="DD-MM-YYYY"
      maxLength={10} value={text} aria-invalid={!!error}
      aria-describedby={[props["aria-describedby"], error ? errorId : ""].filter(Boolean).join(" ") || undefined}
      onChange={(event) => {
        const next = event.target.value;
        setText(next);
        const iso = next ? parseDisplayDate(next) : "";
        let message = next && !iso ? "Enter a valid date as DD-MM-YYYY." : "";
        if (iso && min && iso < min) message = `Date must be on or after ${formatDate(min)}.`;
        if (iso && max && iso > max) message = `Date must be on or before ${formatDate(max)}.`;
        setError(message);
        event.target.setCustomValidity(message);
        if (!message) onValueChange(iso || "");
      }} />
      <button type="button" className="btn" style={{ marginLeft: 4, padding: 6 }}
        aria-label={`Open calendar for ${props["aria-label"] || "date"}`} title="Choose date"
        disabled={props.disabled || props.readOnly}
        onClick={() => {
          if (picker.current?.showPicker) picker.current.showPicker();
          else picker.current?.click();
        }}>
        <CalendarDays size={18} aria-hidden="true" />
      </button>
      <input ref={picker} type="date" tabIndex={-1} aria-hidden="true"
        style={{ position: "absolute", left: 0, bottom: 0, width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
        value={value} min={min} max={max} disabled={props.disabled || props.readOnly}
        onChange={(event) => {
          if (!event.currentTarget.validity.valid) return;
          const iso = event.currentTarget.value;
          setText(formatDate(iso, ""));
          setError("");
          input.current?.setCustomValidity("");
          onValueChange(iso);
          input.current?.focus();
        }} />
    </span>
    {error && <span id={errorId} role="alert" style={{ color: "var(--danger)", fontSize: 12 }}>{error}</span>}
  </span>;
}
