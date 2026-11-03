import ro from "../assets/flags/ro.svg";
import it from "../assets/flags/it.svg";
import cn from "../assets/flags/cn.svg";
import type { Environment } from "../api/auth";

const flags: Record<string, string> = { ro, it, cn };

export default function EnvironmentLabel({ environment }: { environment: Environment }) {
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
    <img src={flags[environment.flag_key]} alt="" aria-hidden="true" width={24} height={16} />
    <span>{environment.label}</span>
  </span>;
}
