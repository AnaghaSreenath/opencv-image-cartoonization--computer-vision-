from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12MB upload limit
PROCESS_MAX_DIMENSION = 1280

CONTROL_SPECS: list[dict[str, Any]] = [
    {
        "name": "downsample_levels",
        "label": "Downsample levels",
        "min": 0,
        "max": 3,
        "default": 2,
        "step": 1,
        "odd": False,
    },
    {
        "name": "bilateral_passes",
        "label": "Bilateral passes",
        "min": 1,
        "max": 12,
        "default": 7,
        "step": 1,
        "odd": False,
    },
    {
        "name": "sigma_color",
        "label": "Color smoothness",
        "min": 10,
        "max": 250,
        "default": 75,
        "step": 1,
        "odd": False,
    },
    {
        "name": "sigma_space",
        "label": "Spatial smoothness",
        "min": 10,
        "max": 250,
        "default": 75,
        "step": 1,
        "odd": False,
    },
    {
        "name": "median_blur",
        "label": "Median blur size",
        "min": 3,
        "max": 11,
        "default": 7,
        "step": 2,
        "odd": True,
    },
    {
        "name": "adaptive_block_size",
        "label": "Adaptive block size",
        "min": 3,
        "max": 21,
        "default": 9,
        "step": 2,
        "odd": True,
    },
    {
        "name": "adaptive_c",
        "label": "Adaptive constant (C)",
        "min": 0,
        "max": 20,
        "default": 2,
        "step": 1,
        "odd": False,
    },
    {
        "name": "edge_blur",
        "label": "Outline blur size",
        "min": 1,
        "max": 11,
        "default": 3,
        "step": 2,
        "odd": True,
    },
    {
        "name": "canny_threshold_1",
        "label": "Canny threshold 1",
        "min": 0,
        "max": 255,
        "default": 60,
        "step": 1,
        "odd": False,
    },
    {
        "name": "canny_threshold_2",
        "label": "Canny threshold 2",
        "min": 0,
        "max": 255,
        "default": 150,
        "step": 1,
        "odd": False,
    },
    {
        "name": "edge_dilate",
        "label": "Outline thickness",
        "min": 0,
        "max": 5,
        "default": 1,
        "step": 1,
        "odd": False,
    },
]

CONTROL_MAP = {control["name"]: control for control in CONTROL_SPECS}


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def normalize_odd(value: int, lower: int, upper: int) -> int:
    normalized = clamp(value, lower, upper)
    if normalized % 2 == 0:
        normalized = normalized - 1 if normalized == upper else normalized + 1
    return clamp(normalized, lower, upper)


def parse_int_control(name: str, raw_value: str | None) -> int:
    spec = CONTROL_MAP[name]
    if raw_value in (None, ""):
        return int(spec["default"])
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid value for {name}.") from exc

    if spec["odd"]:
        return normalize_odd(value, int(spec["min"]), int(spec["max"]))
    return clamp(value, int(spec["min"]), int(spec["max"]))


def parse_bool(raw_value: str | None) -> bool:
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "on", "yes"}


def parse_controls(form_data: dict[str, str]) -> dict[str, int | bool]:
    parsed: dict[str, int | bool] = {}
    for spec in CONTROL_SPECS:
        parsed[spec["name"]] = parse_int_control(spec["name"], form_data.get(spec["name"]))
    parsed["invert_outline"] = parse_bool(form_data.get("invert_outline"))
    return parsed


def decode_uploaded_image(uploaded_file: Any) -> np.ndarray:
    buffer = np.frombuffer(uploaded_file.read(), dtype=np.uint8)
    if buffer.size == 0:
        raise ValueError("Uploaded file is empty.")
    decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("Unsupported image format. Use PNG or JPG.")
    return decoded


def resize_for_processing(image: np.ndarray, max_dimension: int) -> np.ndarray:
    height, width = image.shape[:2]
    longest_side = max(height, width)
    if longest_side <= max_dimension:
        return image

    scale = max_dimension / float(longest_side)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def extract_outline(image: np.ndarray, controls: dict[str, int | bool]) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edge_blur = int(controls["edge_blur"])
    if edge_blur > 1:
        gray = cv2.GaussianBlur(gray, (edge_blur, edge_blur), 0)

    edges = cv2.Canny(
        gray,
        threshold1=int(controls["canny_threshold_1"]),
        threshold2=int(controls["canny_threshold_2"]),
    )

    dilation = int(controls["edge_dilate"])
    if dilation > 0:
        edges = cv2.dilate(edges, None, iterations=dilation)

    if bool(controls["invert_outline"]):
        edges = cv2.bitwise_not(edges)
    return edges


def cartoonize_image(image: np.ndarray, controls: dict[str, int | bool]) -> np.ndarray:
    downsample_levels = int(controls["downsample_levels"])
    bilateral_passes = int(controls["bilateral_passes"])
    sigma_color = int(controls["sigma_color"])
    sigma_space = int(controls["sigma_space"])

    color = image.copy()
    for _ in range(downsample_levels):
        color = cv2.pyrDown(color)

    for _ in range(bilateral_passes):
        color = cv2.bilateralFilter(color, d=9, sigmaColor=sigma_color, sigmaSpace=sigma_space)

    for _ in range(downsample_levels):
        color = cv2.pyrUp(color)

    if color.shape[:2] != image.shape[:2]:
        color = cv2.resize(
            color,
            (image.shape[1], image.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, int(controls["median_blur"]))

    edges = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        int(controls["adaptive_block_size"]),
        int(controls["adaptive_c"]),
    )

    edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    return cv2.bitwise_and(color, edges_color)


def encode_png_data_url(image: np.ndarray) -> str:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Failed to encode image.")
    base64_payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/png;base64,{base64_payload}"


@app.get("/")
def index() -> str:
    return render_template("index.html", controls=CONTROL_SPECS)


@app.post("/api/process")
def process_image() -> tuple[Any, int] | Any:
    if "image" not in request.files:
        return jsonify({"error": "Please upload an image."}), 400

    uploaded = request.files["image"]
    if uploaded.filename.strip() == "":
        return jsonify({"error": "Please choose an image file."}), 400

    try:
        controls = parse_controls(request.form)
        image = decode_uploaded_image(uploaded)
        image = resize_for_processing(image, PROCESS_MAX_DIMENSION)
        outline = extract_outline(image, controls)
        cartoon = cartoonize_image(image, controls)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except cv2.error:
        return jsonify({"error": "OpenCV processing failed for this image."}), 400

    return jsonify(
        {
            "outline_image": encode_png_data_url(outline),
            "cartoon_image": encode_png_data_url(cartoon),
            "processed_width": int(image.shape[1]),
            "processed_height": int(image.shape[0]),
        }
    )


@app.errorhandler(413)
def payload_too_large(_: Exception) -> tuple[Any, int]:
    return jsonify({"error": "Image is too large. Maximum upload size is 12MB."}), 413


if __name__ == "__main__":
    app.run(debug=True)
