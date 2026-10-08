"""Security self-check. Run from backend/:  python test_security.py
Uses a throwaway SQLite file, never dimarcy.db."""
import io
import os
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com", ADMIN_PASSWORD="admin-pass",
                  RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import MAX_BODY_BYTES, app  # noqa: E402

_buf = io.BytesIO()
Image.new("RGB", (1200, 1800), "#7a3b2e").save(_buf, "JPEG")  # a real photo-shaped JPEG (portrait 2:3)
JPEG = _buf.getvalue()

with TestClient(app) as c:
    admin = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
        "email": "admin@test.com", "password": "admin-pass"}).json()["access_token"]}
    c.post("/api/users", headers=admin, json={"name": "Vend", "email": "v@test.com", "password": "seller-pass"})
    seller = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
        "email": "v@test.com", "password": "seller-pass"}).json()["access_token"]}

    # API docs / route map hidden
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404

    # every data route needs a token
    for path in ("/api/customers", "/api/orders", "/api/products", "/api/colors", "/api/users", "/api/dashboard"):
        assert c.get(path).status_code == 401, path

    # sellers can read the catalog but not change it; only admins can
    product = {"reference": "R1", "description": "Blusão", "price": 10}
    assert c.get("/api/products", headers=seller).status_code == 200
    assert c.post("/api/products", headers=seller, json=product).status_code == 403
    assert c.post("/api/colors", headers=seller, json={"name": "Bordô"}).status_code == 403
    assert c.get("/api/users", headers=seller).status_code == 403
    pid = c.post("/api/products", headers=admin, json=product).json()["id"]

    # SQL injection in search is just text, not SQL
    r = c.get("/api/products", headers=admin, params={"search": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json() == []

    # an image named .html is stored as .jpg and served with nosniff
    r = c.post(f"/api/products/{pid}/image", headers=admin, files={"file": ("x.html", JPEG, "text/html")})
    url = r.json()["image_url"]
    assert url.endswith(".jpg"), url
    assert c.get(url).headers["x-content-type-options"] == "nosniff"
    assert c.post(f"/api/products/{pid}/image", headers=admin,
                  files={"file": ("x.jpg", b"<script>alert(1)</script>", "image/jpeg")}).status_code == 400

    # a JPEG header followed by garbage is not a readable image
    assert c.post(f"/api/products/{pid}/image", headers=admin,
                  files={"file": ("x.jpg", b"\xff\xd8\xff\xe0" + b"0" * 100, "image/jpeg")}).status_code == 400

    # every photo gets a small thumbnail for lists; the original is kept as is for zoom
    tmp = c.post("/api/products", headers=admin, json={**product, "reference": "R-del"}).json()["id"]
    up = c.post(f"/api/products/{tmp}/image", headers=admin, files={"file": ("x.jpg", JPEG, "image/jpeg")}).json()
    full, thumb = c.get(up["image_url"]), c.get(up["thumb_url"])
    assert full.status_code == thumb.status_code == 200 and full.content == JPEG
    assert Image.open(io.BytesIO(thumb.content)).size == (320, 480)
    assert len(thumb.content) < len(JPEG)

    # replacing the photo deletes the old pair; deleting the product deletes the new pair (no orphans)
    up2 = c.post(f"/api/products/{tmp}/image", headers=admin, files={"file": ("y.jpg", JPEG, "image/jpeg")}).json()
    assert c.get(up["image_url"]).status_code == c.get(up["thumb_url"]).status_code == 404
    assert c.delete(f"/api/products/{tmp}", headers=admin).status_code == 204
    assert c.get(up2["image_url"]).status_code == c.get(up2["thumb_url"]).status_code == 404

    # photos uploaded before thumbnails existed get one at startup
    from app.routers.products import UPLOAD_DIR
    from app.uploads import backfill_thumbs, thumb_name
    old = UPLOAD_DIR / "999999_test-old-photo.jpg"
    old.write_bytes(JPEG)
    try:
        backfill_thumbs(UPLOAD_DIR)
        assert (UPLOAD_DIR / thumb_name(old.name)).is_file()
    finally:
        old.unlink(missing_ok=True)
        (UPLOAD_DIR / thumb_name(old.name)).unlink(missing_ok=True)

    # oversized body rejected, with and without Content-Length
    big = b"x" * (MAX_BODY_BYTES + 1)
    assert c.post("/api/auth/login", content=big, headers={"Content-Type": "application/json"}).status_code == 413
    assert c.post("/api/auth/login", content=iter([big]),
                  headers={"Content-Type": "application/json"}).status_code == 413

    # brute force: 5 wrong passwords lock the account, even the right one is refused
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "v@test.com", "password": "nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "v@test.com", "password": "seller-pass"}).status_code == 429

print("security checks OK")
