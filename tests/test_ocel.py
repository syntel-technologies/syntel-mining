"""OCEL 2.0 JSON: every reference checked on read, canonical on write, flattened per object type."""

from __future__ import annotations

import json
from typing import Any

import pytest

from syntel_mining.ocel import OcelError, dump, dumps, load, traces, variants

LOG: dict[str, Any] = json.loads("""
{
  "objectTypes": [
    {"name": "application", "attributes": [{"name": "fee", "type": "float"}]},
    {"name": "officer", "attributes": []}
  ],
  "eventTypes": [
    {"name": "submit", "attributes": []},
    {"name": "check", "attributes": []},
    {"name": "approve", "attributes": [{"name": "channel", "type": "string"}]}
  ],
  "objects": [
    {"id": "app-2", "type": "application",
     "attributes": [{"name": "fee", "time": "2026-09-01T00:00:00Z", "value": 150.0}], "relationships": []},
    {"id": "app-1", "type": "application", "attributes": [],
     "relationships": [{"objectId": "off-1", "qualifier": "assigned"}]},
    {"id": "off-1", "type": "officer", "attributes": [], "relationships": []}
  ],
  "events": [
    {"id": "e3", "type": "approve", "time": "2026-09-03T10:00:00+04:00",
     "attributes": [{"name": "channel", "value": "portal"}],
     "relationships": [{"objectId": "app-1", "qualifier": "application"},
                       {"objectId": "off-1", "qualifier": "approver"}]},
    {"id": "e1", "type": "submit", "time": "2026-09-01T09:00:00Z", "attributes": [],
     "relationships": [{"objectId": "app-1", "qualifier": "application"}]},
    {"id": "e2", "type": "check", "time": "2026-09-02T09:00:00Z", "attributes": [],
     "relationships": [{"objectId": "app-1", "qualifier": "application"},
                       {"objectId": "off-1", "qualifier": "checker"}]},
    {"id": "e4", "type": "submit", "time": "2026-09-02T12:00:00Z", "attributes": [],
     "relationships": [{"objectId": "app-2", "qualifier": "application"}]}
  ]
}
""")


def test_a_log_reads_and_writes_back_canonically() -> None:
    first = dumps(load(LOG))
    assert dumps(load(first)) == first
    written = dump(load(LOG))
    assert [o["id"] for o in written["objects"]] == ["app-1", "app-2", "off-1"]
    assert [e["id"] for e in written["events"]] == ["e1", "e2", "e4", "e3"]
    assert written["events"][-1]["time"] == "2026-09-03T06:00:00Z"


def test_each_object_type_flattens_to_its_own_traces() -> None:
    log = load(LOG)
    assert {k: [e.id for e in v] for k, v in traces(log, "application").items()} == {
        "app-2": ["e4"],
        "app-1": ["e1", "e2", "e3"],
    }
    assert variants(log, "application") == {("submit", "check", "approve"): 1, ("submit",): 1}
    assert variants(log, "officer") == {("check", "approve"): 1}


def test_every_broken_reference_is_named() -> None:
    broken = json.loads(json.dumps(LOG))
    broken["events"][0]["relationships"].append({"objectId": "ghost", "qualifier": "x"})
    broken["events"][1]["type"] = "undeclared"
    broken["objects"][2]["id"] = "app-1"
    broken["events"][2]["time"] = "yesterday"
    with pytest.raises(OcelError) as raised:
        load(broken)
    problems = " | ".join(raised.value.problems)
    assert "missing object 'ghost'" in problems
    assert "type 'undeclared' is not declared" in problems
    assert "repeats one" in problems
    assert "not ISO 8601" in problems
