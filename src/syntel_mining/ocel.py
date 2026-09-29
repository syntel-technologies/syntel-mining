"""OCEL 2.0 in its JSON form: read with every reference checked, written deterministically, flattened per type.

Written from the published specification (A. Berti et al., "OCEL (Object-Centric Event Log) 2.0 Specification",
2024, https://www.ocel-standard.org). A log declares its object types and event types with their attributes;
objects carry attribute values over time and qualified relationships to other objects (O2O); events carry a
time, attribute values and qualified relationships to objects (E2O). Reading refuses a log whose relationships
name missing objects, whose objects or events name undeclared types, whose ids repeat or whose times do not
parse: an event log that is wrong is worse than none.

`traces` flattens the log for one object type, which is how the inductive miner, alignments and DECLARE see it:
each object's events in time order (ties by event id), as activity names.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

TYPES = frozenset({"string", "time", "integer", "float", "boolean"})


class OcelError(ValueError):
    """The log is not a valid OCEL 2.0 log; `problems` says every way it is not."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""))
        self.problems = problems


@dataclass(frozen=True)
class Relationship:
    object_id: str
    qualifier: str = ""


@dataclass(frozen=True)
class ObjectValue:
    name: str
    time: datetime
    value: Any


@dataclass
class Object:
    id: str
    type: str
    attributes: list[ObjectValue] = field(default_factory=list[ObjectValue])
    relationships: list[Relationship] = field(default_factory=list[Relationship])


@dataclass
class Event:
    id: str
    type: str
    time: datetime
    attributes: dict[str, Any] = field(default_factory=dict[str, Any])
    relationships: list[Relationship] = field(default_factory=list[Relationship])


@dataclass
class Ocel:
    #: type name → {attribute name → attribute type}
    object_types: dict[str, dict[str, str]] = field(default_factory=dict[str, dict[str, str]])
    event_types: dict[str, dict[str, str]] = field(default_factory=dict[str, dict[str, str]])
    objects: dict[str, Object] = field(default_factory=dict[str, Object])
    events: list[Event] = field(default_factory=list[Event])


def _time(value: object, where: str, problems: list[str]) -> datetime:
    try:
        at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        problems.append(f"{where}: time {value!r} is not ISO 8601")
        return datetime.fromtimestamp(0, UTC)
    if at.tzinfo is None:
        problems.append(f"{where}: time {value!r} has no offset")
        return at.replace(tzinfo=UTC)
    return at


def _list(value: object) -> list[Mapping[str, Any]]:
    return (
        [cast("Mapping[str, Any]", v) for v in cast("list[Any]", value) if isinstance(v, Mapping)]
        if isinstance(value, list)
        else []
    )


def _types(raw: object, kind: str, problems: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for t in _list(raw):
        name = str(t.get("name", ""))
        if not name or name in out:
            problems.append(f"{kind} {name!r} is unnamed or declared twice")
            continue
        attrs: dict[str, str] = {}
        for a in _list(t.get("attributes")):
            if a.get("type") not in TYPES:
                problems.append(f"{kind} {name!r}: attribute {a.get('name')!r} has type {a.get('type')!r}")
            attrs[str(a.get("name"))] = str(a.get("type"))
        out[name] = attrs
    return out


def _relationships(raw: object) -> list[Relationship]:
    return [Relationship(str(r.get("objectId")), str(r.get("qualifier") or "")) for r in _list(raw)]


def load(data: str | bytes | Mapping[str, Any]) -> Ocel:
    """An OCEL 2.0 JSON log, every reference checked; raises OcelError with every problem found."""
    raw = cast("Mapping[str, Any]", json.loads(data) if isinstance(data, str | bytes) else data)
    problems: list[str] = []
    log = Ocel(
        object_types=_types(raw.get("objectTypes"), "object type", problems),
        event_types=_types(raw.get("eventTypes"), "event type", problems),
    )
    for o in _list(raw.get("objects")):
        oid, otype = str(o.get("id", "")), str(o.get("type", ""))
        if not oid or oid in log.objects:
            problems.append(f"object {oid!r} has no id or repeats one")
            continue
        if otype not in log.object_types:
            problems.append(f"object {oid!r}: type {otype!r} is not declared")
        values = [
            ObjectValue(str(a.get("name")), _time(a.get("time"), f"object {oid!r}", problems), a.get("value"))
            for a in _list(o.get("attributes"))
        ]
        log.objects[oid] = Object(oid, otype, values, _relationships(o.get("relationships")))
    seen: set[str] = set()
    for e in _list(raw.get("events")):
        eid, etype = str(e.get("id", "")), str(e.get("type", ""))
        if not eid or eid in seen:
            problems.append(f"event {eid!r} has no id or repeats one")
            continue
        seen.add(eid)
        if etype not in log.event_types:
            problems.append(f"event {eid!r}: type {etype!r} is not declared")
        attrs = {str(a.get("name")): a.get("value") for a in _list(e.get("attributes"))}
        log.events.append(
            Event(
                eid,
                etype,
                _time(e.get("time"), f"event {eid!r}", problems),
                attrs,
                _relationships(e.get("relationships")),
            )
        )
    for o in log.objects.values():
        problems.extend(
            f"object {o.id!r} relates to missing object {r.object_id!r}"
            for r in o.relationships
            if r.object_id not in log.objects
        )
    for e in log.events:
        problems.extend(
            f"event {e.id!r} relates to missing object {r.object_id!r}"
            for r in e.relationships
            if r.object_id not in log.objects
        )
    if problems:
        raise OcelError(problems)
    return log


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def dump(log: Ocel) -> dict[str, Any]:
    """The log as OCEL 2.0 JSON, in a canonical order (types and objects by name and id, events by time and id)."""

    def types(declared: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {"name": n, "attributes": [{"name": a, "type": t} for a, t in sorted(attrs.items())]}
            for n, attrs in sorted(declared.items())
        ]

    def rels(rs: list[Relationship]) -> list[dict[str, str]]:
        return [
            {"objectId": r.object_id, "qualifier": r.qualifier}
            for r in sorted(rs, key=lambda r: (r.object_id, r.qualifier))
        ]

    return {
        "objectTypes": types(log.object_types),
        "eventTypes": types(log.event_types),
        "objects": [
            {
                "id": o.id,
                "type": o.type,
                "attributes": [
                    {"name": v.name, "time": _iso(v.time), "value": v.value}
                    for v in sorted(o.attributes, key=lambda v: (v.time, v.name))
                ],
                "relationships": rels(o.relationships),
            }
            for o in sorted(log.objects.values(), key=lambda o: o.id)
        ],
        "events": [
            {
                "id": e.id,
                "type": e.type,
                "time": _iso(e.time),
                "attributes": [{"name": k, "value": v} for k, v in sorted(e.attributes.items())],
                "relationships": rels(e.relationships),
            }
            for e in sorted(log.events, key=lambda e: (e.time, e.id))
        ],
    }


def dumps(log: Ocel) -> str:
    return json.dumps(dump(log), ensure_ascii=False, separators=(",", ":"))


def traces(log: Ocel, object_type: str) -> dict[str, list[Event]]:
    """Each object of the type with its events in time order (ties by event id): the log flattened for one type."""
    if object_type not in log.object_types:
        raise KeyError(object_type)
    out: dict[str, list[Event]] = {o.id: [] for o in log.objects.values() if o.type == object_type}
    for e in sorted(log.events, key=lambda e: (e.time, e.id)):
        for oid in dict.fromkeys(r.object_id for r in e.relationships):
            if oid in out:
                out[oid].append(e)
    return out


def variants(log: Ocel, object_type: str) -> Counter[tuple[str, ...]]:
    """The activity sequences of one object type and how many objects followed each."""
    return Counter(tuple(e.type for e in events) for events in traces(log, object_type).values())


__all__ = [
    "Event",
    "Object",
    "ObjectValue",
    "Ocel",
    "OcelError",
    "Relationship",
    "dump",
    "dumps",
    "load",
    "traces",
    "variants",
]
