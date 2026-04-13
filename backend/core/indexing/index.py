from pathlib import Path
from typing import Sequence

from PIL import Image

from backend.core.indexing.index_faces import index_face_batch
from backend.core.indexing.index_images import coerce_image_paths
from backend.core.indexing.index_images import index_image_batch
from backend.core.indexing.index_images import prepare_image_paths
from backend.core.models.faces.detector import load_face_detector
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import save_face_vector_stores
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import save_image_vector_store


IMAGE_SUFFIXES = {suffix.lower() for suffix in Image.registered_extensions()}


def _list_folder_files(folder_path: Path, *, recursive: bool) -> list[Path]:
    iterator = folder_path.rglob("*") if recursive else folder_path.iterdir()
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _chunk_paths(paths: Sequence[Path], batch_size: int) -> list[list[Path]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    return [list(paths[start : start + batch_size]) for start in range(0, len(paths), batch_size)]


def index_batch(
    image_paths: Sequence[str | Path],
    image_model: BaseEmbeddingModel,
    *,
    batch_size: int = 32,
    save_after_batch: bool = False,
) -> dict:
    normalized_paths = coerce_image_paths(image_paths)
    valid_paths, failed_items = prepare_image_paths(normalized_paths)

    stats = {
        "input_count": len(normalized_paths),
        "processed_count": len(valid_paths),
        "failed_count": len(failed_items),
        "failed_items": failed_items,
        "image_indexing": {},
        "face_indexing": {},
        "total_people_in_batch": 0,
        "new_people_count": 0,
    }

    if not valid_paths:
        return stats

    image_model.load_model()
    load_face_detector()
    load_face_embedding_model()

    image_stats = index_image_batch(
        image_model,
        valid_paths,
        validate_inputs=False,
    )
    face_stats = index_face_batch(
        valid_paths,
        embedding_batch_size=batch_size,
        validate_inputs=False,
    )

    stats["image_indexing"] = image_stats
    stats["face_indexing"] = face_stats
    stats["total_people_in_batch"] = int(face_stats.get("assigned_person_count", 0))
    stats["new_people_count"] = int(face_stats.get("new_person_count", 0))
    stats["person_store_total"] = int(face_stats.get("person_store_total", 0))

    if save_after_batch:
        save_image_vector_store()
        save_face_vector_stores()

    return stats


def index_folder(
    folder_path: str | Path,
    image_model: BaseEmbeddingModel,
    *,
    batch_size: int = 64,
    recursive: bool = True,
    save_after_batch: bool = False,
) -> dict:
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder}")

    discovered_files = _list_folder_files(folder, recursive=recursive)
    batches = _chunk_paths(discovered_files, batch_size) if discovered_files else []

    stats = {
        "folder_path": str(folder),
        "recursive": recursive,
        "batch_size": batch_size,
        "discovered_file_count": len(discovered_files),
        "batch_count": len(batches),
        "processed_count": 0,
        "failed_count": 0,
        "failed_items": [],
        "image_indexed_count": 0,
        "face_indexed_count": 0,
        "total_people_in_batches": 0,
        "new_people_count": 0,
        "final_person_store_total": 0,
        "completion_count": 0,
        "completion_percent": 0.0,
        "batches": [],
    }

    for batch_index, batch_paths in enumerate(batches, start=1):
        batch_stats = index_batch(
            batch_paths,
            image_model,
            batch_size=batch_size,
            save_after_batch=save_after_batch,
        )

        stats["processed_count"] += int(batch_stats.get("processed_count", 0))
        stats["failed_count"] += int(batch_stats.get("failed_count", 0))
        stats["failed_items"].extend(batch_stats.get("failed_items", []))
        stats["image_indexed_count"] += int(batch_stats.get("image_indexing", {}).get("indexed_count", 0))
        stats["face_indexed_count"] += int(batch_stats.get("face_indexing", {}).get("indexed_face_count", 0))
        stats["total_people_in_batches"] += int(batch_stats.get("total_people_in_batch", 0))
        stats["new_people_count"] += int(batch_stats.get("new_people_count", 0))
        stats["final_person_store_total"] = int(batch_stats.get("person_store_total", stats["final_person_store_total"]))
        stats["completion_count"] += len(batch_paths)
        if stats["discovered_file_count"] > 0:
            stats["completion_percent"] = round(
                (stats["completion_count"] / stats["discovered_file_count"]) * 100,
                2,
            )
        stats["batches"].append(
            {
                "batch_index": batch_index,
                "batch_file_count": len(batch_paths),
                "completion_count": stats["completion_count"],
                "completion_percent": stats["completion_percent"],
                "stats": batch_stats,
            }
        )
        print("*"*40)
        print(f"Completed batch {batch_index}/{stats['batch_count']} - {stats['completion_percent']}% complete")
        print(f"Batch stats: {batch_stats}")

    save_image_vector_store()
    save_face_vector_stores()
    return stats
