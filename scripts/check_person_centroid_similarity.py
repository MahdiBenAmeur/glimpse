from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch
from PIL import Image

from backend.config import PERSON_VS_PATH

# Adjust this threshold to control which nearest-neighbor links are considered
# strong enough to become merge candidates.
MERGE_SIMILARITY_THRESHOLD = 0.50

DEFAULT_OUTPUT_DIR = Path("scripts/person_merge_groups")


def _load_person_metadata(store_path: Path) -> dict:
    meta_data_path = store_path / "meta_data.json"
    with meta_data_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid metadata format in {meta_data_path}")
    return payload


def _load_person_centroids(person_meta_data: dict) -> tuple[list[int], torch.Tensor]:
    person_items: list[tuple[int, list[float]]] = []
    for key, value in person_meta_data.items():
        if str(key).startswith("_"):
            continue
        if not isinstance(value, dict):
            continue

        person_id = int(key)
        centroid = value.get("centroid")
        if not isinstance(centroid, list) or not centroid:
            continue
        person_items.append((person_id, centroid))

    if not person_items:
        return [], torch.empty((0, 0), dtype=torch.float32)

    person_items.sort(key=lambda item: item[0])
    person_ids = [person_id for person_id, _centroid in person_items]
    centroids = torch.tensor([centroid for _person_id, centroid in person_items], dtype=torch.float32)
    centroids = torch.nn.functional.normalize(centroids, dim=1)
    return person_ids, centroids


def _format_score(score: float) -> str:
    return f"{score:.6f}"


def _sanitize_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "unknown"


def _clamp_box(box: list[float], width: int, height: int) -> tuple[int, int, int, int] | None:
    if len(box) != 4:
        return None
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1 + 1, min(x2, width))
    y2 = max(y1 + 1, min(y2, height))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _extract_representative_face(person_id: int, person_entry: dict, destination_path: Path) -> bool:
    image_paths = person_entry.get("image_paths") or []
    face_boxes = person_entry.get("face_boxes") or []

    for image_path_value, face_box in zip(image_paths, face_boxes):
        image_path = Path(str(image_path_value))
        if not image_path.exists():
            continue
        if not isinstance(face_box, list):
            continue

        try:
            with Image.open(image_path) as image:
                rgb_image = image.convert("RGB")
                clamped_box = _clamp_box(face_box, *rgb_image.size)
                if clamped_box is None:
                    continue
                crop = rgb_image.crop(clamped_box)
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                crop.save(destination_path, format="JPEG", quality=95)
                return True
        except Exception:
            continue

    return False


def _build_merge_groups(
    person_ids: list[int],
    best_indices: torch.Tensor,
    best_scores: torch.Tensor,
    *,
    threshold: float,
) -> list[list[int]]:
    adjacency: dict[int, set[int]] = {person_id: set() for person_id in person_ids}

    for row_index, person_id in enumerate(person_ids):
        best_score = float(best_scores[row_index].item())
        if best_score < threshold:
            continue

        best_match_index = int(best_indices[row_index].item())
        best_match_person_id = person_ids[best_match_index]
        adjacency[person_id].add(best_match_person_id)
        adjacency[best_match_person_id].add(person_id)

    visited: set[int] = set()
    groups: list[list[int]] = []

    for person_id in person_ids:
        if person_id in visited or not adjacency[person_id]:
            continue

        stack = [person_id]
        component: list[int] = []
        visited.add(person_id)

        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        groups.append(sorted(component))

    groups.sort(key=lambda group: (group[0], len(group)))
    return groups


def _export_group_previews(groups: list[list[int]], person_meta_data: dict, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_count = 0

    for group_index, group in enumerate(groups, start=1):
        group_dir = output_dir / f"group_{group_index:03d}"
        group_dir.mkdir(parents=True, exist_ok=True)

        for person_id in group:
            person_entry = person_meta_data.get(str(person_id), {})
            representative_path = group_dir / f"person_{_sanitize_filename(str(person_id))}.jpg"
            if _extract_representative_face(person_id, person_entry, representative_path):
                exported_count += 1

    return exported_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print nearest person centroids and export merge groups as preview folders.",
    )
    parser.add_argument(
        "--store-path",
        default=PERSON_VS_PATH,
        help="Person vector store path. Defaults to the configured PERSON_VS_PATH.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Folder where final merge groups will be exported as image previews.",
    )
    args = parser.parse_args()

    store_path = Path(args.store_path)
    output_dir = Path(args.output_dir)

    if not store_path.exists():
        print(f"Person vector store not found at: {store_path}")
        return 1
    if not (store_path / "meta_data.json").exists():
        print(f"Person centroid metadata not found at: {store_path / 'meta_data.json'}")
        return 1

    person_meta_data = _load_person_metadata(store_path)
    person_ids, centroids = _load_person_centroids(person_meta_data)
    if not person_ids:
        print("No person centroids found.")
        return 0

    if len(person_ids) == 1:
        print(f"Loaded 1 person centroid from: {store_path}")
        print(f"Merge similarity threshold: {MERGE_SIMILARITY_THRESHOLD}")
        print(f"person_id={person_ids[0]} most_similar_person_id=None similarity=None")
        print()
        print("final_merge_groups")
        print("No merge groups found above the threshold.")
        return 0

    similarity_matrix = centroids @ centroids.T
    similarity_matrix.fill_diagonal_(-1.0)
    best_scores, best_indices = torch.max(similarity_matrix, dim=1)

    print(f"Loaded {len(person_ids)} person centroids from: {store_path}")
    print(f"Merge similarity threshold: {MERGE_SIMILARITY_THRESHOLD}")
    print("person_id\tmost_similar_person_id\tsimilarity")
    for row_index, person_id in enumerate(person_ids):
        best_match_index = int(best_indices[row_index].item())
        best_match_person_id = person_ids[best_match_index]
        best_score = float(best_scores[row_index].item())
        print(f"{person_id}\t{best_match_person_id}\t{_format_score(best_score)}")

    merge_groups = _build_merge_groups(
        person_ids,
        best_indices,
        best_scores,
        threshold=MERGE_SIMILARITY_THRESHOLD,
    )

    print()
    print("final_merge_groups")
    if not merge_groups:
        print("No merge groups found above the threshold.")
        return 0

    for group_index, group in enumerate(merge_groups, start=1):
        formatted_group = ", ".join(str(person_id) for person_id in group)
        print(f"group_{group_index}\t[{formatted_group}]")

    exported_count = _export_group_previews(merge_groups, person_meta_data, output_dir)
    print()
    print(f"Exported {exported_count} representative face image(s) to: {output_dir.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
