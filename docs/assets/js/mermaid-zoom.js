// Click-to-zoom for Mermaid diagrams.
// Clicking a diagram opens a fullscreen overlay with the SVG fitted to the viewport.
// Clicking the overlay or pressing Escape closes it.

document.addEventListener("click", function (e) {
  var mermaid = e.target.closest(".mermaid");
  if (!mermaid) return;
  if (e.target.closest(".mermaid-fullscreen-overlay")) return;

  var overlay = document.createElement("div");
  overlay.className = "mermaid-fullscreen-overlay";

  var clone = document.createElement("div");
  clone.className = "mermaid-clone";
  clone.innerHTML = mermaid.innerHTML;

  // Remove inline width/height from the cloned SVG so CSS can control sizing
  var svg = clone.querySelector("svg");
  if (svg) {
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.style.maxWidth = "95vw";
    svg.style.maxHeight = "85vh";
    svg.style.width = "auto";
    svg.style.height = "auto";
  }

  overlay.appendChild(clone);
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  function close() {
    overlay.remove();
    document.body.style.overflow = "";
  }

  overlay.addEventListener("click", function (ev) {
    if (ev.target === overlay || ev.target.closest(".mermaid-clone")) close();
  });

  document.addEventListener("keydown", function handler(ev) {
    if (ev.key === "Escape") {
      close();
      document.removeEventListener("keydown", handler);
    }
  });
});
