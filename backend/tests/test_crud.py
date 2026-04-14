import httpx

BASE_URL = "http://127.0.0.1:8000/api"

def test_collections():
    print("\n=== Testing Collections ===")

    # Create
    payload = {"name": "My Test Collection", "description": "Demo collection"}
    r = httpx.post(f"{BASE_URL}/collections/", json=payload)
    print("Create:", r.status_code, r.json())
    collection_id = r.json()["id"]

    # Read all
    r = httpx.get(f"{BASE_URL}/collections/")
    print("Read all:", r.status_code, r.json())

    # Read one
    r = httpx.get(f"{BASE_URL}/collections/{collection_id}")
    print("Read one:", r.status_code, r.json())

    # Update
    payload = {"description": "Updated description"}
    r = httpx.patch(f"{BASE_URL}/collections/{collection_id}", json=payload)
    print("Update:", r.status_code, r.json())

    """# Delete
    r = httpx.delete(f"{BASE_URL}/collections/{collection_id}")
    print("Delete:", r.status_code, r.json())"""


def test_folders():
    print("\n=== Testing Folders API ===")

    # 1. Create
    payload = {
        "path": "/images/folder1",
        "image_count": 0,
        "status": "new",
        "include_subfolders": True
    }
    r = httpx.post(f"{BASE_URL}/folders/", json=payload)
    print("Create:", r.status_code, r.json())
    folder_id = r.json()["id"]

    # 2. Read all
    r = httpx.get(f"{BASE_URL}/folders/")
    print("Read all:", r.status_code, r.json())

    # 3. Read one
    r = httpx.get(f"{BASE_URL}/folders/{folder_id}")
    print("Read one:", r.status_code, r.json())

    # 4. Update
    payload = {"status": "updated", "image_count": 5}
    r = httpx.patch(f"{BASE_URL}/folders/{folder_id}", json=payload)
    print("Update:", r.status_code, r.json())

    # 5. Delete
    r = httpx.delete(f"{BASE_URL}/folders/{folder_id}")
    print("Delete:", r.status_code, r.json())


def test_people():
    print("\n=== Testing People API ===")

    # 1. Create
    payload = {
        "face_url": "http://example.com/face.jpg",
        "id": 1
    }
    r = httpx.post(f"{BASE_URL}/people/", json=payload)
    print("Create:", r.status_code, r.json())
    person_id = r.json()["id"]

    # 2. Read all
    r = httpx.get(f"{BASE_URL}/people/")
    print("Read all:", r.status_code, r.json())

    # 3. Read one
    r = httpx.get(f"{BASE_URL}/people/{person_id}")
    print("Read one:", r.status_code, r.json())

    # 4. Update
    payload = {"face_url": "http://example.com/new_face.jpg"}
    r = httpx.patch(f"{BASE_URL}/people/{person_id}", json=payload)
    print("Update:", r.status_code, r.json())

    # 5. Delete
    r = httpx.delete(f"{BASE_URL}/people/{person_id}")
    print("Delete:", r.status_code, r.json())


def test_images():
    print("\n=== Testing Images ===")
    payload = {"id": "image1", "url": "http://example.com/img.jpg", "filename": "img.jpg"}
    r = httpx.post(f"{BASE_URL}/images/", json=payload)
    print("Create:", r.status_code, r.json())
    image_id = r.json()["id"]

    r = httpx.get(f"{BASE_URL}/images/{image_id}")
    print("Read one:", r.status_code, r.json())


if __name__ == "__main__":
    #test_collections()
    #test_folders()
    test_people()
