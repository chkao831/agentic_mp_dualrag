# ADR-NNNN: [short title]

Architecture decision description template after **Jeff Tyree and Art Akerman**, *Architecture Decisions: Demystifying Architecture* (Capital One). See also project requirements: [`doc/requirements.md`](../requirements.md).

---

## Issue

Describe the architectural design issue you are addressing, leaving no questions about **why** this issue matters **now**. Follow a minimalist approach: document only what must be decided at this point in the life cycle.

---

## Decision

State clearly the architecture’s **direction**—the position selected (not a menu of options; those belong under **Positions**).

---

## Status

Examples: `pending` · `decided` · `approved` · `deprecated` · `superseded by ADR-XXXX`

---

## Group

Simple grouping helps organize the decision set, e.g. **integration**, **presentation**, **data**, **security**, **operations**.

*(Optional: a finer ontology—e.g. event, calendar, location—if the program uses one.)*

---

## Assumptions

State assumptions about the **environment** in which the decision is made: cost, schedule, technology, team skills, vendor roadmaps, etc.

Note: **Environmental constraints** (enterprise standards, mandated patterns, approved stacks) may **bound** which alternatives are even considered.

---

## Constraints

Capture **additional constraints** that the chosen alternative imposes on the environment (new standards, mandatory patterns, operational duties, etc.).

---

## Positions

List **viable alternatives** considered. This list need not be exhaustive, but it should be defensible—you want to avoid “Did you think about…?” in late reviews without credible answers. Stating alternatives explicitly helps enroll advocates of other options.

---

## Argument

Explain **why** the selected position wins: implementation cost, TCO, time to market, risk, availability of skills, alignment with constraints, etc. This section is as important as **Decision** for organizational buy-in.

---

## Implications

A decision triggers follow-on effects (per metamodels such as REMAP), for example:

- Triggers further architecture or product decisions
- Creates or changes **functional** or **non-functional** requirements
- Adds constraints or negotiation points (scope, schedule, customers)
- Implies training, staffing, or process change

State implications clearly to support roadmaps and execution.

---

## Related decisions

List ADRs or decisions that **depend on** or **constrain** this one. For complex programs, a **traceability matrix**, decision tree, or metamodel diagram may supplement this list.

---

## Related requirements

Decisions should be **business and requirement driven**. Map to IDs in [`doc/requirements.md`](../requirements.md) (e.g. `FR-01`, `NFR-02`).

If a decision does **not** advance a stated requirement, reconsider whether it should be taken.

---

## Related artifacts

Architecture / design / scope documents **affected** by this decision (paths, wiki links, APIs).

---

## Related principles

If the enterprise uses **architecture or engineering principles**, state which principles this decision **supports** or **interprets**. Use `N/A` if none are formally adopted for this effort.

---

## Notes

Capture discussion points, open questions, and **socialization** notes while the decision is pending (meetings can span weeks).
