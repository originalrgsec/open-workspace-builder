// Click-to-zoom for Mermaid diagrams.
// Clicking a diagram opens a fullscreen overlay with the SVG scaled up.
// Clicking the overlay or pressing Escape closes it.

document.addEventListener("click", function (e) {
  var mermaid = e.target.closest(".mermaid");
  if (!mermaid) return;

  // Don't open if already in overlay
  if (e.target.closest(".mermaid-fullscreen-overlay")) return;

  var overlay = document.createElement("div");
  overlay.className = "mermaid-fullscreen-overlay";

  var clone = document.createElement("div");
  clone.className = "mermaid-clone";
  clone.innerHTML = mermaid.innerHTML;

  overlay.appendChild(clone);
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  function close() {
    overlay.remove();
    document.body.style.overflow = "";
  }

  overlay.addEventListener("click", function (ev) {
    if (ev.target === overlay) close();
  });

  document.addEventListener("keydown", function handler(ev) {
    if (ev.key === "Escape") {
      close();
      document.removeEventListener("keydown", handler);
    }
  });
});
