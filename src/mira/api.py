"""Knowledge API shared by snapshot and journaled live persistence."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict

from .format import (Equation, Memory, Relationship, Unit, base36, parse, render,
                     require, validate_corpus)
from .index import SemanticDirectory
from .store import ConflictError, SnapshotStore


class Knowledge:
    def __init__(self, root="knowledge", embedding=None, *, store=None):
        self.store = store if store is not None else SnapshotStore(root)
        self.directory = SemanticDirectory(self.store, embedding)

    def transaction(self, operation, *, files=None, operation_type="knowledge",
                    context=None, expected_revision=None, fault=None):
        """Commit a validated batch through the live store.

        operation mutates the existing Memory/Equation lists and identity ledger.
        files contains JSON text for state/results/events, committed in the same
        operation. The callback runs under the writer lock; it must not call back
        into Knowledge. Returns only after the durable commit marker.
        """
        require(getattr(self.store, "live", False), "batch transaction requires live store")
        with self.store.lock():
            revision, memories, equations, ledger = self.store.read()
            if expected_revision is not None and revision != expected_revision:
                raise ConflictError("live transaction revision changed")
            result = operation(memories, equations, ledger)
            self.store.publish(memories, equations, ledger, revision, fault,
                               files=files, operation_type=operation_type, context=context)
            return deepcopy(result)

    def _mutate(self, operation, fault=None):
        with self.store.lock():
            generation, memories, equations, ledger = self.store.read()
            result = operation(memories, equations, ledger)
            self.store.publish(memories, equations, ledger, generation, fault)
            # Indexes are rebuilt lazily under the same lock by all query entrypoints.
            # A failure here cannot make a successfully published commit look aborted.
            return deepcopy(result)

    def create_memory(self, title, summary, *, kind="research", metadata=None):
        require(kind in {"research", "synthesis"}, "memory kind")
        def create(memories, equations, ledger):
            prefix = "r" if kind == "research" else "s"
            identity = prefix + base36(ledger[prefix])
            ledger[prefix] += 1
            memory = Memory(identity, title, summary, metadata=metadata or {})
            memories.append(memory)
            return memory
        return self._mutate(create)

    def document(self, identity):
        with self.store.lock():
            for memory in self.store.read()[1]:
                if memory.id == identity:
                    return memory
        raise KeyError(identity)

    def _edit(self, identity, change, expected_revision=None, fault=None):
        def edit(memories, equations, ledger):
            memory = next((m for m in memories if m.id == identity), None)
            if memory is None:
                raise KeyError(identity)
            if expected_revision is not None and memory.revision != expected_revision:
                raise ConflictError("newer document revision exists")
            result = change(memory, equations)
            memory.revision += 1
            return result
        return self._mutate(edit, fault)

    def add_finding(self, document, label, proposition, explanation, provenance, *, kind="claim", evidence_status="unverified", expected_revision=None):
        def add(memory, equations):
            unit = Unit(memory.allocate("f"), label, {"Kind": kind, "Evidence status": evidence_status,
                        "Proposition": proposition, "Explanation": explanation, "Provenance": provenance})
            memory.units.append(unit)
            return memory.id + "#" + unit.anchor
        return self._edit(document, add, expected_revision)

    def add_question(self, document, label, question, *, state="open", expected_revision=None):
        def add(memory, equations):
            unit = Unit(memory.allocate("q"), label, {"Question": question, "State": state})
            memory.units.append(unit)
            return memory.id + "#" + unit.anchor
        return self._edit(document, add, expected_revision)

    def add_equation(self, document, label, expression, variables, assumptions, provenance, *, units=None, expected_revision=None):
        def add(memory, equations):
            anchor = memory.allocate("e")
            identity = f"e_{memory.id}_{int(anchor[1:], 36)}"
            equations.append(Equation(identity, memory.id, label, expression, variables, assumptions, provenance, units=units or {}))
            memory.units.append(Unit(anchor, label, {"Equation": identity}))
            return identity
        return self._edit(document, add, expected_revision)

    def reference_equation(self, document, equation_id, label, *, expected_revision=None):
        def add(memory, equations):
            unit = Unit(memory.allocate("e"), label, {"Equation": equation_id})
            memory.units.append(unit)
            return memory.id + "#" + unit.anchor
        return self._edit(document, add, expected_revision)

    def add_relationship(self, document, source, type, target, *, status="proposed", expected_revision=None):
        def add(memory, equations):
            edge = Relationship(source, type, target, status)
            memory.relationships.append(edge)
            return edge
        return self._edit(document, add, expected_revision)

    def save_memory(self, memory, *, expected_revision, fault=None):
        """Save a detached draft with CAS. Existing unit edits are rejected."""
        draft = deepcopy(memory)
        def change(current, equations):
            require(draft.id == current.id, "document identity changed")
            current.title = draft.title
            current.summary = draft.summary
            current.metadata = draft.metadata
            current.next_ids = draft.next_ids
            current.units = draft.units
            current.relationships = draft.relationships
            return current
        return self._edit(draft.id, change, expected_revision, fault)

    def retrieve(self, reference):
        with self.store.lock():
            _, memories, equations, _ = self.store.read()
            docs, eqs, units, _ = validate_corpus(memories, equations)
            if reference in eqs:
                return asdict(eqs[reference])
            if reference in docs:
                return render(docs[reference])
            if reference in units:
                memory, unit = units[reference]
                result = {"id": reference, "document": memory.id, **asdict(unit), "revision": unit.revision}
                if unit.kind == "equation":
                    result["definition"] = asdict(eqs[unit.fields["Equation"]])
                return result
        raise KeyError(reference)

    def containing_document(self, reference):
        record = self.directory.exact(reference)
        if record is None:
            raise KeyError(reference)
        return self.retrieve(record["document"])

    def validate(self, text=None):
        with self.store.lock():
            _, memories, equations, _ = self.store.read()
            if text is not None:
                memory = parse(text)
                memories = [m for m in memories if m.id != memory.id] + [memory]
            docs, eqs, units, edges = validate_corpus(memories, equations)
            return {"documents": len(docs), "equations": len(eqs), "units_including_documents": len(units), "relationships": len(edges)}

    def relationships(self, reference, **kwargs):
        return self.directory.relationships(reference, **kwargs)

    def search(self, query, **kwargs):
        return self.directory.search(query, **kwargs)

    def summaries(self):
        return self.directory.summaries()

    def rebuild(self):
        return self.directory.rebuild()
