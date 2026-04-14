from pathlib import Path

from PIL import Image, ImageDraw

from backend.core.indexing.index import index_folder
from backend.core.models.vision_language.siglip import SiglipEmbeddingModel
from backend.core.search.search import global_search, search_by_face, search_by_person_id
from backend.core.models.vision_language.clip import ClipEmbeddingModel

def test_index_folder():
    folder_path = "test_images"
    #siglipmodel = SiglipEmbeddingModel()
    clipmodel = ClipEmbeddingModel()
    stats = index_folder(folder_path, image_model=clipmodel, batch_size=4, save_after_batch=False)

    print(stats)

def test_search():
    siglipmodel = SiglipEmbeddingModel()

    query = r"test_images\image0.png"
    results = search_by_face(query, top_k=10)
    print(results)


def test_global_search():
    siglipmodel = SiglipEmbeddingModel()

    examples = [
        {
            "name": "1) Basic text global search",
            "params": {
                "query": "a portrait photo of a person",
                "image_model": siglipmodel,
                "k": 10,
                "page_number": 1,
                "face_presence": "any",
            },
        },
        {
            "name": "2) Pagination (page 2)",
            "params": {
                "query": "a portrait photo of a person",
                "image_model": siglipmodel,
                "k": 10,
                "page_number": 2,
                "face_presence": "any",
            },
        },
        {
            "name": "3) Folder + date cutoff + must contain faces",
            "params": {
                "query": "outdoor person photo",
                "image_model": siglipmodel,
                "k": 10,
                "page_number": 1,
                "folders": [r"test_images"],
                "date_cutoff": "2023-01-01",
                "face_presence": "contains_faces",
            },
        },
        {
            "name": "4) Per-person face filters",
            "params": {
                "query": "group photo",
                "image_model": siglipmodel,
                "k": 10,
                "page_number": 1,
                "face_presence": "any",
                "person_filters": [
                    {"person_id": 2, "preference": "must_include"},
                    {"person_id": 4, "preference": "prefer"},
                    {"person_id": 1, "preference": "exclude"},
                ],
            },
        },
        {
            "name": "5) Text + face-photo merge",
            "params": {
                "query": "portrait close-up",
                "image_model": siglipmodel,
                "k": 10,
                "page_number": 1,
                "face_presence": "any",
                "face_photo_path": r"test_images\image0.png",
            },
        },
    ]

    for example in examples:
        print("=" * 80)
        print(example["name"])
        result = global_search(**example["params"])
        print(
            {
                "total_results": result.get("total_results"),
                "total_pages": result.get("total_pages"),
                "page_number": result.get("page_number"),
                "result_count_on_page": len(result.get("results", [])),
            }
        )
        print("Top 3:")
        for item in result.get("results", [])[:3]:
            print(
                {
                    "image_id": item.get("image_id"),
                    "image_path": item.get("image_path"),
                    "final_score": item.get("final_score"),
                    "person_ids": item.get("person_ids"),
                }
            )


def test_person_id_boxed_images(person_id: int, max_images: int = 30):
    person_meta = search_by_person_id(person_id)
    image_paths = person_meta.get("image_paths", [])
    face_boxes = person_meta.get("face_boxes", [])

    output_dir = Path("artifacts") / "person_id_previews" / f"person_id_{person_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        {
            "person_id": person_id,
            "person_count": person_meta.get("count"),
            "total_images": len(image_paths),
            "total_boxes": len(face_boxes),
            "output_dir": str(output_dir),
        }
    )

    saved = 0
    for idx, image_path in enumerate(image_paths):
        if saved >= max_images:
            break

        image_file = Path(image_path)
        if not image_file.exists():
            continue

        try:
            with Image.open(image_file) as image:
                preview = image.convert("RGB")
                draw = ImageDraw.Draw(preview)

                if idx < len(face_boxes):
                    box = face_boxes[idx]
                    if isinstance(box, (list, tuple)) and len(box) == 4:
                        x1, y1, x2, y2 = [int(round(v)) for v in box]
                        draw.rectangle((x1, y1, x2, y2), outline="red", width=4)

                out_path = output_dir / f"{saved:03d}_{image_file.stem}_boxed.jpg"
                preview.save(out_path, "JPEG", quality=95)
                print(f"saved: {out_path}")
                saved += 1
        except Exception as exc:
            print(f"failed: {image_file} ({exc})")

    print({"saved_count": saved})


if __name__ == "__main__":
    test_index_folder()
    #test_person_id_boxed_images(person_id=0, max_images=10)
    #siglipmodel  = ClipEmbeddingModel()
    #print(global_search("happy", image_model=siglipmodel, k=10, page_number=1, face_presence="any", person_filters = [{"person_id": 2, "preference": "exclude"}]))
