import { createContext, useContext } from "react";
import type { Lang, Me, Meta, Person, Region, TypeSchema } from "../lib/types";

export interface UserCtx {
  meta: Meta;
  me: Me;
  persons: Person[];
  person: Person | null; // currently selected
  selectPerson: (id: string) => void;
  reloadPersons: () => Promise<void>;
  reloadMe: () => Promise<void>;
  schema: TypeSchema[];
  regions: Region[];
  lang: Lang;
  logout: () => Promise<void>;
}

export const Ctx = createContext<UserCtx | null>(null);

export function useUser(): UserCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useUser outside provider");
  return c;
}

export function regionLabel(regions: Region[], ref: unknown, lang: Lang, t: (k: string) => string): string {
  const str = typeof ref === "string" ? ref : (ref as { region?: string })?.region ?? "";
  const [id, side] = str.split(":");
  const r = regions.find((x) => x.id === id);
  const name = r ? r.labels[lang] : id;
  return side ? `${name} (${t(`form.${side}`)})` : name;
}
