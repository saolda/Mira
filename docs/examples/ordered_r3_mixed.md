# Research: How do the synthetic results, equation and figure relate?

```json
{
  "id": "r1",
  "metadata": {
    "created_order": 1,
    "evidence_ref": "research/results/batch.json",
    "kind": "research",
    "node_id": "q1",
    "source_memories": [],
    "synthesized_by": null
  },
  "next": {
    "e": 2,
    "f": 3,
    "i": 2,
    "q": 1
  },
  "revision": 1,
  "summary": "A scoped finding",
  "version": 1
}
```

## Memory

[#f1] A scoped finding

**Kind:** finding

**Evidence status:** unverified

**Proposition:** A scoped finding

**Explanation:** Synthetic fixture, not empirical evidence.

**Provenance:** Supplied source identifiers: source-a. Model extraction; not independently verified.

[#e1] Mass-energy expression

**Equation:** e_r1_1

**Description:** Mass-energy expression

**Expression:**

$$
E = mc^2
$$

**Variables:**

- E: Energy (units: joules)
- c: Speed of light (units: not supplied)
- m: Mass (units: kilograms)

**Provenance:** Supplied source identifiers: source-a. Model extraction; not independently verified. Equation origin: source (model-reported, unverified).

[#i1] Synthetic caption

**Image:** ![Synthetic caption](<https://example.org/fig2.png>)

**Figure reference:** Figure 2

**Provenance:** Supplied source identifiers: source-a. Model extraction; not independently verified.

[#f2] A scoped hypothesis

**Kind:** hypothesis

**Evidence status:** unverified

**Proposition:** A scoped hypothesis

**Explanation:** Synthetic fixture, not empirical evidence.

**Provenance:** Supplied source identifiers: source-a. Model extraction; not independently verified.

## Relationships

```json
{
  "relationships": [
    {
      "from": "f1",
      "status": "unverified",
      "to": "https://example.org/paper",
      "type": "CITES"
    },
    {
      "from": "e1",
      "status": "unverified",
      "to": "https://example.org/paper",
      "type": "CITES"
    },
    {
      "from": "i1",
      "status": "unverified",
      "to": "https://example.org/paper",
      "type": "CITES"
    },
    {
      "from": "f2",
      "status": "unverified",
      "to": "https://example.org/paper",
      "type": "CITES"
    },
    {
      "from": "e1",
      "status": "unverified",
      "to": "r1#f1",
      "type": "RELATED_TO"
    },
    {
      "from": "i1",
      "status": "unverified",
      "to": "r1#f1",
      "type": "RELATED_TO"
    },
    {
      "from": "f2",
      "status": "unverified",
      "to": "r1#f1",
      "type": "RELATED_TO"
    }
  ],
  "version": 1
}
```
