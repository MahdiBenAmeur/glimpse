from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image
from ultralytics import YOLO

from backend.config import DETECTOR_MODEL, FACE_MIN_BOX_SIZE, models_cache_dir , device

def load_face_detector():
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


def detect_faces(image_paths: list[Path], min_box_size: int = FACE_MIN_BOX_SIZE):
    """
    takes in a list of image paths
    returns a dict mapping each image path to a list of bounding boxes (if any)
    """
    if min_box_size < 0:
        raise ValueError("min_box_size must be greater than or equal to 0")

    model = load_face_detector()
    results = model.predict(image_paths, save=False)
    path_2_boxes = {}
    for image_path, result in zip(image_paths, results):
        if result.boxes is not None:
            filtered_boxes = []
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                width = x2 - x1
                height = y2 - y1
                if width >= min_box_size and height >= min_box_size:
                    filtered_boxes.append(box)

            if filtered_boxes:
                path_2_boxes[image_path] = filtered_boxes
    return path_2_boxes

def crop_faces(path_2_boxes)-> dict[Path, list[Image.Image]]:
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
