// Small DOM binding, kept separate so keyboard/outside cleanup is testable.
export function bindNotificationPopover({ browserDocument, container, trigger, panel, close }) {
  const pointer = event => { if (!container.contains(event.target)) close(); };
  const keyboard = event => {
    if (event.key === "Escape") { event.preventDefault(); close(); trigger.focus(); }
  };
  browserDocument.addEventListener("pointerdown", pointer);
  container.addEventListener("keydown", keyboard);
  panel.querySelector("button, a[href]")?.focus();
  return () => {
    browserDocument.removeEventListener("pointerdown", pointer);
    container.removeEventListener("keydown", keyboard);
  };
}
