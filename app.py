from flask import Flask, request, render_template, send_file
from PIL import Image, ImageOps, ImageEnhance
from io import BytesIO

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")


# 🔥 IMPROVED IMAGE PROCESSING (SAFE + BETTER LOOK)
def process_single_image(input_image_bytes):
    import cv2
    import numpy as np
    from PIL import Image
    from io import BytesIO
    from rembg import remove

    # load image
    input_image = Image.open(BytesIO(input_image_bytes)).convert("RGBA")

    # remove background
    output = remove(input_image)

    # convert to OpenCV format
    img = np.array(output)
    gray = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)

    # load face detector
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) > 0:
        (x, y, w, h) = faces[0]

        # expand crop (head + shoulders)
        top = max(0, y - int(0.6 * h))
        bottom = min(img.shape[0], y + int(1.8 * h))
        left = max(0, x - int(0.5 * w))
        right = min(img.shape[1], x + int(1.5 * w))

        cropped = img[top:bottom, left:right]
    else:
        cropped = img  # fallback

    # convert back to PIL
    cropped_pil = Image.fromarray(cropped)

    # white background
    bg = Image.new("RGB", cropped_pil.size, (255, 255, 255))
    bg.paste(cropped_pil, mask=cropped_pil.split()[3])

    return bg


@app.route("/process", methods=["POST"])
def process():
    print("==== /process endpoint hit ====")

    passport_width = int(request.form.get("width", 413))
    passport_height = int(request.form.get("height", 531))
    border = int(request.form.get("border", 2))
    spacing = int(request.form.get("spacing", 20))

    margin_x = 10
    margin_y = 10
    horizontal_gap = 10
    a4_w, a4_h = 2480, 3508

    images_data = []

    i = 0
    while f"image_{i}" in request.files:
        file = request.files[f"image_{i}"]
        copies = int(request.form.get(f"copies_{i}", 6))
        images_data.append((file.read(), copies))
        i += 1

    if not images_data and "image" in request.files:
        file = request.files["image"]
        copies = int(request.form.get("copies", 6))
        images_data.append((file.read(), copies))

    if not images_data:
        return "No image uploaded", 400

    passport_images = []

    for img_bytes, copies in images_data:
        img = process_single_image(img_bytes)
        img = img.resize((passport_width, passport_height), Image.LANCZOS)
        img = ImageOps.expand(img, border=border, fill="black")
        passport_images.append((img, copies))

    paste_w = passport_width + 2 * border
    paste_h = passport_height + 2 * border

    pages = []
    current_page = Image.new("RGB", (a4_w, a4_h), "white")
    x, y = margin_x, margin_y

    def new_page():
        nonlocal current_page, x, y
        pages.append(current_page)
        current_page = Image.new("RGB", (a4_w, a4_h), "white")
        x, y = margin_x, margin_y

    for passport_img, copies in passport_images:
        for _ in range(copies):

            if x + paste_w > a4_w - margin_x:
                x = margin_x
                y += paste_h + spacing

            if y + paste_h > a4_h - margin_y:
                new_page()

            current_page.paste(passport_img, (x, y))
            x += paste_w + horizontal_gap

    pages.append(current_page)

    output = BytesIO()

    if len(pages) == 1:
        pages[0].save(output, format="PDF", dpi=(300, 300))
    else:
        pages[0].save(
            output,
            format="PDF",
            dpi=(300, 300),
            save_all=True,
            append_images=pages[1:]
        )

    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="passport-sheet.pdf",
    )


if __name__ == "__main__":
  import os
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)