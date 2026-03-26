// Click-to-zoom for Mermaid diagrams.
// Clicking a diagram opens a fullscreen overlay with the SVG fitted and centered.
// Clicking the overlay or pressing Escape closes it.

document.addEventListener("click", function (e) {
  var mermaid = e.target.closest(".mermaid");
  if (!mermaid) return;
  if (e.target.closest(".mermaid-fullscreen-overlay")) return;

  var svg = mermaid.querySelector("svg");
  if (!svg) return;

  var overlay = document.createElement("div");
  overlay.className = "mermaid-fullscreen-overlay";

  // Clone just the SVG element
  var svgClone = svg.cloneNode(true);

  // Get the original viewBox or compute one from the SVG's rendered size
  var viewBox = svgClone.getAttribute("viewBox");
  if (!viewBox) {
    var bbox = svg.getBBox();
    viewBox = bbox.x + " " + bbox.y + " " + bbox.width + " " + bbox.height;
    svgClone.setAttribute("viewBox", viewBox);
  }

  // Remove fixed dimensions so it scales to fit the container
  svgClone.removeAttribute("width");
  svgClone.removeAttribute("height");
  svgClone.removeAttribute("style");
  svgClone.setAttribute("preserveAspectRatio", "xMidYMid meet");

  // Parse viewBox to compute aspect ratio
  var vbParts = viewBox.split(/[\s,]+/).map(Number);
  var vbWidth = vbParts[2];
  var vbHeight = vbParts[3];
  var aspect = vbWidth / vbHeight;

  // Compute the largest size that fits within 90vw x 80vh
  var maxW = window.innerWidth * 0.9;
  var maxH = window.innerHeight * 0.8;
  var fitW, fitH;
  if (aspect > maxW / maxH) {
    fitW = maxW;
    fitH = maxW / aspect;
  } else {
    fitH = maxH;
    fitW = maxH * aspect;
  }

  svgClone.style.width = fitW + "px";
  svgClone.style.height = fitH + "px";
  svgClone.style.display = "block";

  overlay.appendChild(svgClone);
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  function close() {
    overlay.remove();
    document.body.style.overflow = "";
  }

  overlay.addEventListener("click", close);

  document.addEventListener("keydown", function handler(ev) {
    if (ev.key === "Escape") {
      close();
      document.removeEventListener("keydown", handler);
    }
  });
});
