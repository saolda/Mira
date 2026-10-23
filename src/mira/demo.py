"""Small authored synthetic corpus; never imports old research memory."""
from __future__ import annotations
from .api import Knowledge
from .embeddings import TestEmbedding
from .format import ValidationError
from .store import ConflictError


def populate(knowledge):
    require_empty = knowledge.summaries()
    if require_empty:
        raise ValueError("demonstration needs an empty store")
    a = knowledge.create_memory("Cooling experiment", "A synthetic study of heat transfer and cooling.")
    b = knowledge.create_memory("Insulation experiment", "A synthetic investigation of thermal insulation.")
    s = knowledge.create_memory("Thermal design synthesis", "Integration of cooling and insulation findings.", kind="synthesis")
    f1 = knowledge.add_finding(a.id, "Heat transfer", "A warmer object transfers thermal energy to cooler surroundings.", "The temperature difference drives heat transfer under the stated conditions.", "Authored synthetic physics fixture.", kind="claim")
    f2 = knowledge.add_finding(a.id, "Cooling rate", "The cooling rate depends on the temperature difference.", "A lumped-temperature model approximates cooling for small internal gradients.", "Authored synthetic model fixture.", kind="hypothesis")
    q = knowledge.add_question(a.id, "Model validity", "When do internal temperature gradients invalidate this approximation?")
    eq = knowledge.add_equation(a.id, "Newton cooling model", "dT/dt = -k(T - T_a)", {"T": "object temperature", "t": "time", "k": "cooling coefficient", "T_a": "ambient temperature"}, ["Uniform object temperature", "Constant ambient temperature"], "Authored model fixture, not an independently verified derivation.", units={"T": "K", "T_a": "K", "t": "s", "k": "s^-1"})
    b1 = knowledge.add_finding(b.id, "Thermal barrier", "Insulation reduces the rate of thermal energy transfer.", "A barrier increases thermal resistance under otherwise comparable conditions.", "Authored synthetic fixture.")
    b2 = knowledge.add_finding(b.id, "Scope limitation", "A cooling approximation may fail with large internal temperature gradients.", "The uniform-temperature assumption then fails.", "Authored synthetic reasoning fixture.", kind="inference")
    knowledge.add_question(b.id, "Barrier choice", "Which barrier provides sufficient thermal resistance?")
    s1 = knowledge.add_finding(s.id, "Thermal design", "Thermal design combines heat transfer mechanisms with insulation choices.", "The integration is a scoped design hypothesis, not a measured performance claim.", "Manual integration of authored fixtures.", kind="synthesis")
    knowledge.add_finding(s.id, "Evaluation needed", "The combined design requires experimental evaluation.", "The fixtures provide no measured system performance.", "Manual review of the fixture limitations.", kind="observation")
    knowledge.reference_equation(s.id, eq, "Reused cooling equation")
    knowledge.add_relationship(a.id, "f1", "CITES", "https://example.org/synthetic-heat-transfer", status="unverified")
    knowledge.add_relationship(a.id, "f2", "DEPENDS_ON", eq, status="reviewed")
    knowledge.add_relationship(b.id, "f2", "QUALIFIES", f2, status="reviewed")
    knowledge.add_relationship(s.id, "f1", "SYNTHESIZES", f1, status="reviewed")
    knowledge.add_relationship(s.id, "f1", "SYNTHESIZES", b1, status="reviewed")
    knowledge.add_relationship(b.id, "f1", "SUPPORTS", f2, status="rejected")
    return {"finding": f1, "question": q, "equation": eq, "synthesis": s1}


def demonstrate(root, embedding=None):
    k = Knowledge(root, embedding or TestEmbedding())
    refs = populate(k)
    counts = k.rebuild()
    incoming = k.relationships(refs["finding"], direction="incoming")
    before = {"search": k.search("thermal energy"), "incoming": incoming, "summaries": k.summaries(), "vector": k.search("thermal insulation", mode="vector", limit=3)}
    k.directory.path.unlink()
    rebuilt = k.rebuild()
    after = {"search": k.search("thermal energy"), "incoming": k.relationships(refs["finding"], direction="incoming"), "summaries": k.summaries(), "vector": k.search("thermal insulation", mode="vector", limit=3)}
    errors = {}
    try:
        k.add_relationship("r1", "f1", "BUILDS_ON", "rzz#f1")
    except ValidationError as exc:
        errors["invalid_target"] = str(exc)
    draft = k.document("r1")
    k.add_question("r1", "Another test question", "What measurements are needed?")
    try:
        k.save_memory(draft, expected_revision=draft.revision)
    except ConflictError as exc:
        errors["stale_write"] = str(exc)
    current = k.store.current()
    draft = k.document("r1")
    draft.title = "Unpublished title"
    def interrupt(stage):
        if stage == "staged":
            raise RuntimeError("simulated interruption before pointer publication")
    try:
        k.save_memory(draft, expected_revision=draft.revision, fault=interrupt)
    except RuntimeError as exc:
        errors["interruption"] = str(exc)
    return {"corpus": "authored synthetic fixtures; citations are not real evidence",
            "initial_counts": counts, "rebuilt_counts": rebuilt, "equivalent_rebuild": before == after,
            "references": refs, "incoming": incoming,
            "lexical_hits": [r["id"] for r in before["search"]],
            "vector_backend": k.directory.model,
            "vector_hits": [{key: r[key] for key in ("id", "score")} for r in before["vector"]],
            "document_summaries": [r["id"] for r in before["summaries"]],
            "equation_retrieved": k.retrieve(refs["equation"]),
            "errors_detected": errors, "interrupted_snapshot_unchanged": current == k.store.current(),
            "unpublished_snapshots": len(k.store.recovery_status()["unpublished"]),
            "integrity": k.directory.integrity()}
