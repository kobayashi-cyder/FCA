from __future__ import annotations

import csv
import gzip
from hashlib import sha256
import io
import json
import math
from pathlib import Path


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


_CODEX_ID_COLUMNS = ("root_id", "root", "pt_root_id")
_CODEX_PRE_COLUMNS = ("pre_root_id", "pre_pt_root_id", "pre_id")
_CODEX_POST_COLUMNS = ("post_root_id", "post_pt_root_id", "post_id")
_CODEX_WEIGHT_COLUMNS = ("syn_count", "synapse_count", "weight", "n_syn")


def flywire_codex_files_to_manifest(
    connections_path: str | Path,
    annotations_path: str | Path,
    *,
    version: str,
    source_name: str,
    annotation_column: str,
    pre_labels: set[str] | frozenset[str],
    post_labels: set[str] | frozenset[str],
    post_class: str = "KC",
    min_synapses: float = 1.0,
    max_selected_ids: int = 200_000,
    max_candidate_pairs: int = 2_000_000,
    max_units: int = 200_000,
) -> str:
    """Stream FlyWire Codex CSV/CSV.GZ exports into an FCA manifest.

    The annotation file selects presynaptic and postsynaptic root IDs by exact
    values in one caller-chosen column. The connection table is then streamed and
    only selected pairs are aggregated. Pair synapse counts are summed across
    rows/neuropils before the threshold is applied.

    This function never downloads data and never assumes a specific biological
    label means PN/KC; the caller supplies the annotation column and labels.
    """
    connections = Path(connections_path).expanduser()
    annotations = Path(annotations_path).expanduser()
    if not connections.is_file() or not annotations.is_file():
        raise ValueError("Codex connections and annotations files must exist")
    if not str(version).strip() or not str(source_name).strip():
        raise ValueError("version and source_name are required")
    annotation_column = str(annotation_column or "").strip()
    post_class = str(post_class or "").strip()
    if not annotation_column or not post_class:
        raise ValueError("annotation_column and post_class are required")

    pre_values = _normalized_label_set(pre_labels, "pre_labels")
    post_values = _normalized_label_set(post_labels, "post_labels")
    threshold = float(min_synapses)
    if not math.isfinite(threshold) or threshold < 0.0:
        raise ValueError("min_synapses must be finite and non-negative")
    if not 1 <= int(max_selected_ids) <= 1_000_000:
        raise ValueError("max_selected_ids must be in [1, 1000000]")
    if not 1 <= int(max_candidate_pairs) <= 20_000_000:
        raise ValueError("max_candidate_pairs must be in [1, 20000000]")
    if not 1 <= int(max_units) <= 1_000_000:
        raise ValueError("max_units must be in [1, 1000000]")

    pre_ids, post_ids = _codex_select_ids(
        annotations,
        annotation_column=annotation_column,
        pre_labels=pre_values,
        post_labels=post_values,
        max_selected_ids=int(max_selected_ids),
    )
    pair_weights = _codex_selected_pair_weights(
        connections,
        pre_ids=pre_ids,
        post_ids=post_ids,
        max_candidate_pairs=int(max_candidate_pairs),
    )

    retained = {
        pair: weight
        for pair, weight in pair_weights.items()
        if weight >= threshold
    }
    if not retained:
        raise ValueError("no selected Codex connections meet min_synapses")

    used_pre = sorted({pre for pre, _ in retained})
    pre_index = {root_id: i for i, root_id in enumerate(used_pre)}
    by_post: dict[str, set[int]] = {}
    for pre, post in retained:
        by_post.setdefault(post, set()).add(pre_index[pre])

    if len(by_post) > int(max_units):
        raise ValueError("selected Codex unit count exceeds max_units")

    units = [
        {
            "id": post,
            "class": post_class,
            "inputs": sorted(inputs),
        }
        for post, inputs in sorted(by_post.items())
        if inputs
    ]
    if not units:
        raise ValueError("no connected post units")

    connections_sha = _sha256_path(connections)
    annotations_sha = _sha256_path(annotations)
    provenance = {
        "connections_sha256": connections_sha,
        "annotations_sha256": annotations_sha,
        "annotation_column": annotation_column,
        "pre_labels": sorted(pre_values),
        "post_labels": sorted(post_values),
        "min_synapses": threshold,
    }
    combined_sha = sha256(
        json.dumps(
            provenance,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    raw = {
        "schema": "fca.connectome.v1",
        "version": str(version).strip(),
        "source": {
            "name": str(source_name).strip(),
            "sha256": combined_sha,
            **provenance,
        },
        "input_channels": len(used_pre),
        "input_labels": used_pre,
        "units": units,
    }
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _codex_select_ids(
    path: Path,
    *,
    annotation_column: str,
    pre_labels: frozenset[str],
    post_labels: frozenset[str],
    max_selected_ids: int,
) -> tuple[frozenset[str], frozenset[str]]:
    pre_ids: set[str] = set()
    post_ids: set[str] = set()
    with _open_codex_text(path) as fh:
        reader = csv.DictReader(fh)
        fields = tuple(reader.fieldnames or ())
        root_column = _detect_column(fields, _CODEX_ID_COLUMNS, "root ID")
        if annotation_column not in fields:
            raise ValueError(
                f"annotation CSV is missing requested column {annotation_column}"
            )
        for row in reader:
            root_id = str(row.get(root_column, "") or "").strip()
            label = str(row.get(annotation_column, "") or "").strip()
            if not root_id or not label:
                continue
            if label in pre_labels:
                pre_ids.add(root_id)
            if label in post_labels:
                post_ids.add(root_id)
            if len(pre_ids) > max_selected_ids or len(post_ids) > max_selected_ids:
                raise ValueError("selected annotation IDs exceed max_selected_ids")

    if not pre_ids:
        raise ValueError("no presynaptic IDs matched pre_labels")
    if not post_ids:
        raise ValueError("no postsynaptic IDs matched post_labels")
    return frozenset(pre_ids), frozenset(post_ids)


def _codex_selected_pair_weights(
    path: Path,
    *,
    pre_ids: frozenset[str],
    post_ids: frozenset[str],
    max_candidate_pairs: int,
) -> dict[tuple[str, str], float]:
    pair_weights: dict[tuple[str, str], float] = {}
    with _open_codex_text(path) as fh:
        reader = csv.DictReader(fh)
        fields = tuple(reader.fieldnames or ())
        pre_column = _detect_column(fields, _CODEX_PRE_COLUMNS, "presynaptic ID")
        post_column = _detect_column(fields, _CODEX_POST_COLUMNS, "postsynaptic ID")
        weight_column = _detect_column(fields, _CODEX_WEIGHT_COLUMNS, "synapse count")

        for row in reader:
            pre = str(row.get(pre_column, "") or "").strip()
            post = str(row.get(post_column, "") or "").strip()
            if pre not in pre_ids or post not in post_ids:
                continue
            raw_weight = str(row.get(weight_column, "") or "").strip()
            try:
                weight = float(raw_weight)
            except ValueError as exc:
                raise ValueError("Codex synapse count is not numeric") from exc
            if not math.isfinite(weight) or weight < 0.0:
                raise ValueError("Codex synapse count must be finite and non-negative")
            if weight == 0.0:
                continue
            key = (pre, post)
            if key not in pair_weights and len(pair_weights) >= max_candidate_pairs:
                raise ValueError("selected Codex pairs exceed max_candidate_pairs")
            pair_weights[key] = pair_weights.get(key, 0.0) + weight
    if not pair_weights:
        raise ValueError("no connections matched selected Codex IDs")
    return pair_weights


def _open_codex_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _detect_column(
    fields: tuple[str, ...],
    candidates: tuple[str, ...],
    label: str,
) -> str:
    for candidate in candidates:
        if candidate in fields:
            return candidate
    raise ValueError(f"Codex CSV is missing a supported {label} column")


def _normalized_label_set(
    labels: set[str] | frozenset[str],
    name: str,
) -> frozenset[str]:
    if not isinstance(labels, (set, frozenset)) or not labels:
        raise ValueError(f"{name} must be a non-empty set")
    normalized = frozenset(str(label).strip() for label in labels)
    if any(not label or len(label) > 256 for label in normalized):
        raise ValueError(f"{name} contains an invalid label")
    if len(normalized) > 10_000:
        raise ValueError(f"{name} exceeds 10000 labels")
    return normalized


def _sha256_path(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
