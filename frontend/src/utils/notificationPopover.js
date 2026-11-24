// Purpose: Keep notification popover data handling and workflow helpers separate from React rendering so callers use consistent rules.
// Small DOM binding, kept separate so keyboard/outside cleanup is testable.
export function bindNotificationPopover({ browserDocument, container, trigger, panel, close }) {
  // Handle outside pointer interaction so the notification popover can close.
  const pointer = event => { if (!container.contains(event.target)) close(); };
  // Handle keyboard interaction for the current menu or popover.
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
