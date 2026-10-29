import { apiFetch } from "./client";
import type { ApiId } from "./client";
import type { Material } from "./materials";

export type Contact = { contact_id: ApiId; name: string | null; email: string; group_name: string; active: boolean };
export type EmailTemplate = { template_id: ApiId; name: string; to_group: string | null; cc_group: string | null; subject_tmpl: string; body_tmpl: string; is_html: boolean; active: boolean };
export type ComponentType = { type_id: ApiId; name: string; slot_key: string | null; active: boolean };
export type Component = { component_id: ApiId; type_id: ApiId; type_name: string; slot_key: string | null; code: string; description: string | null; unit: string | null; active: boolean };
export type Property = { property_id: ApiId; name: string; unit: string | null; active: boolean; sort_order: number | null };
export type ToleranceMode = "absolute" | "percent";
export type ToleranceBound = "warn_low" | "warn_high" | "alarm_low" | "alarm_high";
export type Tolerance = { tolerance_id: ApiId; property_id: ApiId; material_id: ApiId | null; warn_low: number | null; warn_high: number | null; alarm_low: number | null; alarm_high: number | null; reference_value: number | null; warn_low_input: number | null; warn_low_mode: ToleranceMode; warn_high_input: number | null; warn_high_mode: ToleranceMode; alarm_low_input: number | null; alarm_low_mode: ToleranceMode; alarm_high_input: number | null; alarm_high_mode: ToleranceMode; is_custom: boolean };
export type ToleranceUpsert = Pick<Tolerance, "property_id" | "material_id" | "reference_value"> & Record<`${ToleranceBound}_input`, number | null> & Record<`${ToleranceBound}_mode`, ToleranceMode>;

export function mdListMaterials(): Promise<Material[]> { return apiFetch("/api/master-data/materials"); }
export function mdUpsertMaterial(id: ApiId | null, payload: Omit<Material, "material_id" | "component_defaults">): Promise<Material> { return apiFetch(id == null ? "/api/master-data/materials" : `/api/master-data/materials/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteMaterial(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/materials/${id}`, { method: "DELETE" }); }

export function mdListContacts(): Promise<Contact[]> { return apiFetch("/api/master-data/contacts"); }
export function mdUpsertContact(id: ApiId | null, payload: Omit<Contact, "contact_id">): Promise<Contact> { return apiFetch(id == null ? "/api/master-data/contacts" : `/api/master-data/contacts/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteContact(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/contacts/${id}`, { method: "DELETE" }); }

export function mdListTemplates(): Promise<EmailTemplate[]> { return apiFetch("/api/master-data/email-templates"); }
export function mdUpsertTemplate(id: ApiId | null, payload: Omit<EmailTemplate, "template_id">): Promise<EmailTemplate> { return apiFetch(id == null ? "/api/master-data/email-templates" : `/api/master-data/email-templates/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteTemplate(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/email-templates/${id}`, { method: "DELETE" }); }

export function mdListComponentTypes(): Promise<ComponentType[]> { return apiFetch("/api/master-data/component-types"); }
export function mdUpsertComponentType(id: ApiId | null, payload: Omit<ComponentType, "type_id">): Promise<ComponentType> { return apiFetch(id == null ? "/api/master-data/component-types" : `/api/master-data/component-types/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteComponentType(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/component-types/${id}`, { method: "DELETE" }); }

export function mdListComponents(): Promise<Component[]> { return apiFetch("/api/master-data/components"); }
export function mdUpsertComponent(id: ApiId | null, payload: Omit<Component, "component_id" | "type_name" | "slot_key">): Promise<Component> { return apiFetch(id == null ? "/api/master-data/components" : `/api/master-data/components/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteComponent(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/components/${id}`, { method: "DELETE" }); }

export function mdListProperties(): Promise<Property[]> { return apiFetch("/api/master-data/properties"); }
export function mdUpsertProperty(id: ApiId | null, payload: Omit<Property, "property_id">): Promise<Property> { return apiFetch(id == null ? "/api/master-data/properties" : `/api/master-data/properties/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteProperty(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/properties/${id}`, { method: "DELETE" }); }

export function mdListTolerances(): Promise<Tolerance[]> { return apiFetch("/api/master-data/tolerances"); }
export function mdUpsertTolerance(id: ApiId | null, payload: ToleranceUpsert): Promise<Tolerance> { return apiFetch(id == null ? "/api/master-data/tolerances" : `/api/master-data/tolerances/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function mdDeleteTolerance(id: ApiId): Promise<void> { await apiFetch(`/api/master-data/tolerances/${id}`, { method: "DELETE" }); }
