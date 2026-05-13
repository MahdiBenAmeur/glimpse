from pathlib import Path
from datetime import datetime

import torch
from huggingface_hub import hf_hub_download
from PIL import Image
from ultralytics import YOLO

from backend.config import DETECTOR_MODEL, FACE_DETECTION_CONFIDENCE_THRESHOLD, FACE_MIN_BOX_SIZE, models_cache_dir


def _log_face_detector(message: str, **fields) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    suffix = ""
    if fields:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[{timestamp}] [FACE DETECTOR] {message}{suffix}", flush=True)


def _gpu_memory_snapshot() -> dict[str, float | int | str]:
    """Return lightweight CUDA memory counters for detector logs."""
    if not torch.cuda.is_available():
        return {"cuda": "unavailable"}

    return {
        "allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
        "reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
        "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
        "max_reserved_mb": round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2),
    }

def load_face_detector():
    """Load and cache the YOLO face detector used by the face pipeline."""
    global DETECTOR_MODEL
    if DETECTOR_MODEL is not None:
        return DETECTOR_MODEL
    model_path = hf_hub_download(
        repo_id="AdamCodd/YOLOv11n-face-detection",
        filename="model.pt",
        cache_dir=models_cache_dir,
    )

    model = YOLO(model_path  )
    DETECTOR_MODEL = model
    return model


def detect_faces(
    image_paths: list[Path],
    min_box_size: int = FACE_MIN_BOX_SIZE,
    confidence_threshold: float = FACE_DETECTION_CONFIDENCE_THRESHOLD,
):
    """Run YOLO face detection and return filtered boxes keyed by image path.

    Detection uses the configured confidence threshold, then applies a second
    size filter so tiny boxes do not enter the face embedding pipeline. Images
    without any surviving boxes are omitted from the returned mapping.
    """
    if min_box_size < 0:
        raise ValueError("min_box_size must be greater than or equal to 0")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")

    model = load_face_detector()
    _log_face_detector(
        "Calling YOLO predict",
        image_count=len(image_paths),
        confidence_threshold=confidence_threshold,
        min_box_size=min_box_size,
        **_gpu_memory_snapshot(),
    )
    results = model.predict(image_paths, save=False, conf=confidence_threshold)
    _log_face_detector("YOLO predict returned", result_count=len(results), **_gpu_memory_snapshot())
    path_2_boxes = {}
    for image_path, result in zip(image_paths, results):
        if result.boxes is not None:
            filtered_boxes = []
            for box in result.boxes:
                confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 1.0
                if confidence < confidence_threshold:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                width = x2 - x1
                height = y2 - y1
                if width >= min_box_size and height >= min_box_size:
                    filtered_boxes.append(box)

            if filtered_boxes:
                path_2_boxes[image_path] = filtered_boxes
    _log_face_detector(
        "Filtered face detections",
        matched_image_count=len(path_2_boxes),
        matched_face_count=sum(len(boxes) for boxes in path_2_boxes.values()),
        **_gpu_memory_snapshot(),
    )
    return path_2_boxes

def crop_faces(path_2_boxes)-> dict[Path, list[Image.Image]]:
    """Crop detected face boxes into PIL images while preserving source paths."""
    path_2_crops = {}
    for image_path, boxes in path_2_boxes.items():
        image = Image.open(image_path)
        crops = []
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            crop = image.crop((x1, y1, x2, y2))
            crops.append(crop)
        path_2_crops[image_path] = crops
    return path_2_crops
