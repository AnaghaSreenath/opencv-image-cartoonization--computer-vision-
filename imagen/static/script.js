const form = document.getElementById("process-form");
const fileInput = document.getElementById("image");
const statusNode = document.getElementById("status");
const submitButton = document.getElementById("generate-btn");
const originalPreview = document.getElementById("original-preview");
const outlineResult = document.getElementById("outline-result");
const cartoonResult = document.getElementById("cartoon-result");
const outlineDownload = document.getElementById("outline-download");
const cartoonDownload = document.getElementById("cartoon-download");
const uploadTitle = document.getElementById("upload-title");
const uploadSubtitle = document.getElementById("upload-subtitle");

let previewObjectUrl = null;

const clamp = (value, min, max) => Math.max(min, Math.min(value, max));

function normalizeControlValue(slider, rawValue) {
  const min = Number(slider.min);
  const max = Number(slider.max);
  let value = clamp(Math.round(Number(rawValue)), min, max);

  if (slider.dataset.odd === "1" && value % 2 === 0) {
    value = value === max ? value - 1 : value + 1;
  }

  return clamp(value, min, max);
}

function wireDial(slider, numberInput) {
  slider.addEventListener("input", () => {
    numberInput.value = slider.value;
  });

  numberInput.addEventListener("input", () => {
    const normalized = normalizeControlValue(slider, numberInput.value);
    numberInput.value = String(normalized);
    slider.value = String(normalized);
  });
}

document.querySelectorAll(".dial-group").forEach((group) => {
  const slider = group.querySelector(".dial-slider");
  const numberInput = group.querySelector(".dial-value");
  wireDial(slider, numberInput);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (!file) {
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = null;
    }
    originalPreview.removeAttribute("src");
    uploadTitle.textContent = "Upload image";
    uploadSubtitle.textContent = "PNG or JPG · max 12MB";
    return;
  }
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
  }
  previewObjectUrl = URL.createObjectURL(file);
  originalPreview.src = previewObjectUrl;
  uploadTitle.textContent = file.name;
  uploadSubtitle.textContent = "Ready to process";
});

function setStatus(message, isError = false) {
  statusNode.textContent = message;
  statusNode.style.color = isError ? "#b91c1c" : "#6b7280";
}

function showDownload(linkNode, dataUrl, fileName) {
  linkNode.href = dataUrl;
  linkNode.download = fileName;
  linkNode.classList.add("visible");
}

function clearResultLinks() {
  outlineDownload.classList.remove("visible");
  cartoonDownload.classList.remove("visible");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("Please choose an image first.", true);
    return;
  }

  clearResultLinks();
  setStatus("Processing...");
  submitButton.disabled = true;

  const payload = new FormData();
  payload.append("image", file);

  document.querySelectorAll(".dial-slider").forEach((slider) => {
    payload.append(slider.name, slider.value);
  });

  const invertOutline = document.getElementById("invert_outline");
  payload.append("invert_outline", invertOutline.checked ? "true" : "false");

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      body: payload,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to process image.");
    }

    outlineResult.src = data.outline_image;
    cartoonResult.src = data.cartoon_image;
    showDownload(outlineDownload, data.outline_image, "outline.png");
    showDownload(cartoonDownload, data.cartoon_image, "cartoon.png");
    setStatus(`Done (${data.processed_width} x ${data.processed_height}).`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected error";
    setStatus(message, true);
  } finally {
    submitButton.disabled = false;
  }
});
