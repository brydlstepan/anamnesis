# Body regions (draft v1)

- `id` = stable identifier used in records **and** as mesh name in the GLB models.
- **L** = lateral → reference must include a side: `eye:left`, `knee:right`, `ear:both`.
- **P** = internal organ, *projected* onto its surface area in v1 (layered anatomy later).
- **M / F** = present only on male / female body model (other model shows it on nearest generic region).
- Hierarchy (`parent`) is used for filtering: clicking `lower_limb` matches all its children.
- SNOMED CT / FMA code mapping: to be added later (check licence). Labels cs/en live in the i18n files.

## Pseudo-regions
| id | en | cs | notes |
|---|---|---|---|
| `systemic` | Systemic / whole body | Celkové / celé tělo | no location (blood tests, hypertension…); shown as body-wide subtle glow / side badge |
| `skin` | Skin (whole surface) | Kůže (celý povrch) | |

## Head & neck — parent `head_neck`
| id | en | cs | flags |
|---|---|---|---|
| `scalp` | Scalp | Vlasová část hlavy | |
| `forehead` | Forehead | Čelo | |
| `face` | Face | Obličej | |
| `eye` | Eye | Oko | L |
| `ear` | Ear | Ucho | L |
| `nose` | Nose / sinuses | Nos / dutiny | |
| `mouth` | Mouth | Ústa | |
| `teeth` | Teeth | Zuby | |
| `jaw` | Jaw | Čelist | L |
| `throat` | Throat | Krk (hrdlo) | |
| `neck` | Neck (front) | Krk (přední) | |
| `nape` | Nape | Šíje | |
| `brain` | Brain | Mozek | P |
| `thyroid` | Thyroid | Štítná žláza | P |

## Trunk — thorax — parent `thorax`
| id | en | cs | flags |
|---|---|---|---|
| `chest` | Chest | Hrudník | L |
| `breast` | Breast | Prs | L |
| `sternum` | Sternum | Hrudní kost | |
| `ribs` | Ribs | Žebra | L |
| `axilla` | Armpit | Podpaží | L |
| `upper_back` | Upper back | Horní část zad | |
| `shoulder_blade` | Shoulder blade | Lopatka | L |
| `heart` | Heart | Srdce | P |
| `lungs` | Lungs | Plíce | P, L |
| `esophagus` | Esophagus | Jícen | P |

## Trunk — abdomen & pelvis — parent `abdomen_pelvis`
| id | en | cs | flags |
|---|---|---|---|
| `abdomen_upper` | Upper abdomen (epigastric) | Nadbřišek | |
| `abdomen_ruq` | Abdomen, right upper quadrant | Břicho, pravý horní kvadrant | |
| `abdomen_luq` | Abdomen, left upper quadrant | Břicho, levý horní kvadrant | |
| `abdomen_rlq` | Abdomen, right lower quadrant | Břicho, pravý dolní kvadrant | |
| `abdomen_llq` | Abdomen, left lower quadrant | Břicho, levý dolní kvadrant | |
| `navel` | Navel area | Okolí pupku | |
| `flank` | Flank | Bok | L |
| `lower_back` | Lower back | Bedra | |
| `groin` | Groin | Tříslo | L |
| `pelvis` | Pelvis | Pánev | |
| `genitals` | Genitals | Genitál | |
| `buttock` | Buttock | Hýždě | L |
| `sacrum` | Sacrum / tailbone | Kost křížová / kostrč | |
| `liver` | Liver | Játra | P |
| `gallbladder` | Gallbladder | Žlučník | P |
| `stomach` | Stomach | Žaludek | P |
| `pancreas` | Pancreas | Slinivka | P |
| `spleen` | Spleen | Slezina | P |
| `kidney` | Kidney | Ledvina | P, L |
| `bladder` | Bladder | Močový měchýř | P |
| `small_intestine` | Small intestine | Tenké střevo | P |
| `colon` | Colon | Tlusté střevo | P |
| `appendix` | Appendix | Slepé střevo (červovitý přívěsek) | P |
| `rectum` | Rectum / anus | Konečník | P |
| `uterus` | Uterus | Děloha | P, F |
| `ovary` | Ovary | Vaječník | P, L, F |
| `prostate` | Prostate | Prostata | P, M |
| `testis` | Testis | Varle | L, M |

## Spine — parent `spine`
| id | en | cs | flags |
|---|---|---|---|
| `spine_cervical` | Cervical spine | Krční páteř | |
| `spine_thoracic` | Thoracic spine | Hrudní páteř | |
| `spine_lumbar` | Lumbar spine | Bederní páteř | |

## Upper limb — parent `upper_limb` (all L)
| id | en | cs |
|---|---|---|
| `shoulder` | Shoulder | Rameno |
| `upper_arm` | Upper arm | Paže |
| `elbow` | Elbow | Loket |
| `forearm` | Forearm | Předloktí |
| `wrist` | Wrist | Zápěstí |
| `hand` | Hand | Ruka |
| `thumb` | Thumb | Palec ruky |
| `fingers` | Fingers | Prsty ruky |

## Lower limb — parent `lower_limb` (all L)
| id | en | cs |
|---|---|---|
| `hip` | Hip | Kyčel |
| `thigh` | Thigh | Stehno |
| `knee` | Knee | Koleno |
| `shin` | Shin / lower leg (front) | Bérec (přední) |
| `calf` | Calf | Lýtko |
| `ankle` | Ankle | Kotník |
| `heel` | Heel | Pata |
| `foot` | Foot | Chodidlo / noha |
| `toes` | Toes | Prsty nohy |

## Notes for the 3D artist
- Each id above = one mesh (lateral ids = two meshes: `<id>_left`, `<id>_right`).
- Projected organs (P) = a surface patch mesh above the organ, slightly offset, invisible until highlighted.
- Every mesh needs a local frame (origin at centroid, +Z = surface normal outward) for `offset` and GLB overlay anchoring.
- Keep total GLB < 10 MB per sex (Draco/meshopt), target ≤ 60k triangles.
