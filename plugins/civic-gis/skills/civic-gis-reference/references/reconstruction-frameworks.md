# Post-Conflict Reconstruction Frameworks

International standards and conceptual frameworks for property restitution, damage assessment, and reconstruction planning. Reference for `civic-gis:reconstruction-tracker` and related skills.

## Damage Classification Standards

### UN-Habitat damage levels (most widely adopted)

| Level | Definition | GIS treatment |
|---|---|---|
| **No damage** | Building intact, fully usable | `intact` |
| **Light damage** | Cosmetic / non-structural (windows, doors, finishes) | `damaged` (light) |
| **Moderate damage** | Repairable structural elements; can be rebuilt | `damaged` (moderate) |
| **Severe damage** | Major structural failure but footprint partially survives | `damaged` (severe) |
| **Destroyed** | Building footprint <30% remaining; total loss | `destroyed` |
| **Unknown / inaccessible** | Cannot be assessed (security, denied access) | `unknown` |

### USAID / OFDA SDC scales

Sometimes used in humanitarian contexts:

- 5-point scale (1=no damage → 5=destroyed)
- Often combined with hazard exposure (flood depth, blast distance, etc.)

### EMS-98 (European Macroseismic Scale)

For earthquake damage specifically. 5 grades by structural type. Less common for conflict damage.

## Pinheiro Principles (Property Restitution)

UN principles on housing and property restitution for refugees and displaced persons. 23 principles, the load-bearing ones for GIS work:

| Principle | GIS implication |
|---|---|
| **2 — Right to housing and property restitution** | Displaced persons have right to return to their original homes, regardless of current occupation. |
| **12 — Pre-displacement housing/property records** | National authorities must protect and where necessary reconstruct pre-displacement records. **This is what `civic-gis:reconstruction-tracker --baseline` operates on.** |
| **14 — Adequate consultation and participation** | Displaced persons must be consulted in restitution claim resolution. |
| **15 — Housing, land and property records and documentation** | Where original records are destroyed, alternative forms of evidence (witness testimony, secondary documents, oral claims) must be considered. |
| **18 — Legislative measures** | Restitution claims should not be barred by statutes of limitation. |
| **21 — Compensation** | Compensation only when restitution is "factually impossible," not just inconvenient. |

### Practical implications for civic-gis

- **Reconstruction-tracker output should NEVER imply "destroyed = available for redevelopment by anyone."** Default status is "destroyed, awaiting restitution claim."
- **Parcel ownership in current cadastre may differ from pre-conflict ownership.** Both must be tracked.
- **Reports should flag jurisdictions where local law contravenes Pinheiro** (e.g. Decree 66/2012 in Syria, certain post-conflict property laws elsewhere).

## Damage Assessment Workflows

### Field-based

Surveyors visit each parcel, photograph, classify per UN-Habitat scale. Most accurate but slow and security-dependent.

### Remote sensing

- **Pre/post imagery comparison** — change detection on satellite or drone imagery.
- **SAR (Synthetic Aperture Radar)** — works through cloud cover; detects structural changes.
- **Building damage proxy maps** — UNITAR/UNOSAT, World Bank GFDRR produce maps for major events.
- Less accurate per-parcel than field surveys but scalable.

### Hybrid

Remote sensing identifies candidates; field teams verify high-priority parcels. Best practice for large-scale assessments.

`civic-gis:reconstruction-tracker` accepts any of these as the `--damage-layer` input.

## Reconstruction Planning Tools

### "Build back better" principle

Reconstruction should improve pre-disaster conditions, not just restore them. Implications:

- Energy efficiency / climate resilience
- Earthquake / flood resistance
- Universal accessibility
- Modern utilities (sewer, fiber, etc.)

GIS supports this by overlaying hazard maps onto reconstruction parcels — flagging that "this destroyed parcel is in a known flood zone" affects rebuild design.

### Phased reconstruction

Most reconstructions phase by:

1. **Critical infrastructure** (water, power, hospitals, schools) — first 6-12 months
2. **Public buildings** — next 1-2 years
3. **Residential clusters** — 2-5 years, prioritized by displaced-person return demand
4. **Commercial / industrial** — paralleling residential

`civic-gis:reconstruction-tracker` can report progress per phase if parcels are tagged with their phase.

### Master plan integration

Post-conflict cities often need new master plans before reconstruction (different from pre-conflict plan due to changed demographics, infrastructure decisions, etc.). Reconstruction-tracker reports against:

1. Pre-conflict cadastre (baseline)
2. Post-conflict damage layer
3. Current rebuild status
4. Updated master plan (where built / where not yet)

## Common Pitfalls

1. **Confusing "destroyed" with "available."** Destroyed parcels still have legal owners with restitution rights.
2. **Overlooking informal settlements.** Pre-conflict cadastre may not have registered informal/unregistered housing that nonetheless was someone's home.
3. **Statistical bias toward digitally-recorded property.** Households whose records were on paper get underrepresented; reconstruction-tracker should report this gap.
4. **Currency / numeraire shifts.** Pre-conflict valuations are often meaningless in post-conflict economy. Don't report "value lost" without context.
5. **Politicized geometry.** Boundary lines may have been redrawn during conflict (de facto military boundaries, new municipal lines). Always flag jurisdiction.

## Tools and Datasets

- **UNOSAT** — UN satellite imagery analysis for damage maps
- **HOTOSM Tasking Manager** — crowdsourced building footprint mapping
- **OpenStreetMap** — often the most current building footprint dataset
- **Maxar Open Data** — high-res imagery released during major events
- **PlanetScope / Sentinel** — daily medium-res monitoring

## Country Resources

### Syria
- **HRP (Humanitarian Response Plan)** annual UN OCHA report — sectoral damage estimates
- **REACH Initiative** — Syria-focused field assessments + GIS layers
- **World Bank Syria assessment** (2017) — pre-2017 damage baseline
- **Decree 66 (2012) and Law 10 (2018) Syria** — legal framework controversial under Pinheiro; civic-gis-reconstruction-tracker should flag any parcels in zones declared under these laws

### Iraq
- **Iraq Recovery and Reconstruction Trust Fund** — multilateral framework
- **UNDP Funding Facility for Stabilization** — operates in liberated areas

### Lebanon
- **CDR (Council for Development and Reconstruction)** — coordinates post-civil-war and Beirut-blast reconstruction
- **Beirut blast (Aug 2020)** — high-resolution damage maps publicly available
