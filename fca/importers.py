from __future__ import annotations

import csv
from hashlib import sha256
import io
import json


def edge_csv_to_manifest(
    csv_text: str,
    *,
    version: str,
    source_name: str,
    pre_class: str = "PN",
    post_class: str = "KC",
    min_weight: float = 1.0,
) -> str:
    """Convert a normalized edge table into an FCA connectome manifest.

    Required CSV columns:
    pre_id, post_id, pre_class, post_class, weight

    The converter intentionally requires a normalized table rather than pretending
    every external connectome dataset shares the same schema.
    """
    if not version.strip() or not source_name.strip():
        raise ValueError("version and source_name are required")
    if min_weight < 0:
        raise ValueError("min_weight must be non-negative")

    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"pre_id", "post_id", "pre_class", "post_class", "weight"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("CSV is missing required columns")

    edges: list[tuple[str, str, float]] = []
    for row in reader:
        if row["pre_class"].strip() != pre_class or row["post_class"].strip() != post_class:
            continue
        pre = row["pre_id"].strip()
        post = row["post_id"].strip()
        if not pre or not post:
            continue
        try:
            weight = float(row["weight"])
        except ValueError as exc:
            raise ValueError("edge weight is not numeric") from exc
        if weight >= min_weight:
            edges.append((pre, post, weight))

    if not edges:
        raise ValueError("no matching edges")

    pre_ids = sorted({pre for pre, _, _ in edges})
    pre_index = {pre: i for i, pre in enumerate(pre_ids)}
    by_post: dict[str, list[tuple[str, float]]] = {}
    for pre, post, weight in edges:
        by_post.setdefault(post, []).append((pre, weight))

    units = []
    for post in sorted(by_post):
        inputs = sorted({pre_index[pre] for pre, _ in by_post[post]})
        if inputs:
            units.append({"id": post, "class": post_class, "inputs": inputs})

    if not units:
        raise ValueError("no connected post units")

    raw = {
        "schema": "fca.connectome.v1",
        "version": version.strip(),
        "source": {
            "name": source_name.strip(),
            "sha256": sha256(csv_text.encode("utf-8")).hexdigest(),
        },
        "input_channels": len(pre_ids),
        "input_labels": pre_ids,
        "units": units,
    }
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
