export type Lang = "cs" | "en";
export type Role = "owner" | "editor" | "viewer";

export interface Meta {
  name: string;
  version: string;
  admin_path: string;
  oidc_enabled: boolean;
  oidc_display_name: string;
  default_language: Lang;
  languages: Lang[];
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  auth_provider: "local" | "oidc";
  language: Lang | null;
  show_access_log: boolean;
  person_id: string | null;
}

export interface EmergencyContact {
  name: string;
  phone: string;
  relation: string;
}

export interface Person {
  id: string;
  name: string;
  role: Role;
  is_me: boolean;
  birth_date: string | null;
  sex: "male" | "female" | "other" | "unknown" | null;
  body_model: "male" | "female";
  blood_type: string | null;
  emergency_contacts: EmergencyContact[];
  organ_donation: string | null;
}

export interface Region {
  id: string;
  parent: string | null;
  group: boolean;
  lateral: boolean;
  projected: boolean;
  sex: "male" | "female" | null;
  labels: Record<Lang, string>;
}

export type RegionRef = string | { region: string; offset: [number, number, number] };

export interface FieldDef {
  name: string;
  kind:
    | "text" | "textarea" | "date" | "enum" | "number" | "text_or_number" | "regions"
    | "codes" | "tags" | "links" | "list" | "range" | "attachments";
  required: boolean;
  options: string[];
}

export interface TypeSchema {
  type: RecordType;
  fields: FieldDef[];
}

export type RecordType =
  | "condition" | "procedure" | "exam" | "observation" | "medication" | "allergy" | "vaccination" | "document";

export interface Attachment {
  id: string;
  filename: string;
  mime: string;
  size: number;
  url: string;
}

export interface MedRecord {
  id: string;
  person_id: string;
  type: RecordType;
  title: string;
  date: string;
  end_date: string | null;
  status: string | null;
  regions: RegionRef[];
  attachments: Attachment[];
  review_state: "confirmed" | "draft";
  origin: string;
  editable: boolean;
  version: number;
  updated_at: string;
  [field: string]: unknown;
}

export interface Share {
  id: string;
  email: string;
  display_name: string | null;
  role: "viewer" | "editor";
  status: "active" | "pending";
}

export const RECORD_TYPES: RecordType[] = [
  "condition", "procedure", "exam", "observation", "medication", "allergy", "vaccination", "document",
];
