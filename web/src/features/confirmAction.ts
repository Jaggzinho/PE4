/** Native confirmation retains keyboard/screen-reader behavior for destructive actions. */
export function confirmDelete(kind: string, name: string): boolean {
  return window.confirm(`Delete ${kind} “${name}”? This cannot be undone.`);
}
