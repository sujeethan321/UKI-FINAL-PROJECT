export function positionPanel(anchor, size, viewport, align = "end") {
  const margin = 12, gap = 8;
  const width = Math.min(size.width, Math.max(0, viewport.width - margin * 2));
  const below = Math.max(0, viewport.height - anchor.bottom - gap - margin);
  const above = Math.max(0, anchor.top - gap - margin);
  const flip = below < Math.min(size.height, 240) && above > below;
  const maxHeight = Math.max(0, flip ? above : below);
  const height = Math.min(size.height, maxHeight);
  const left = Math.max(margin, Math.min(align === "start" ? anchor.left : anchor.right - width,
    viewport.width - width - margin));
  const top = Math.max(margin, Math.min(flip ? anchor.top - gap - height : anchor.bottom + gap,
    viewport.height - height - margin));
  return { left, top, width, maxHeight, placement: flip ? "top" : "bottom" };
}

export function nextMenuIndex(index, key, length) {
  if (!length) return -1;
  if (key === "Home") return 0;
  if (key === "End") return length - 1;
  if (index < 0) return key === "ArrowUp" ? length - 1 : 0;
  return (index + (key === "ArrowUp" ? -1 : 1) + length) % length;
}

export function bindFloatingPanel({ panel, trigger, close, menu = false, initialFocus = "first" }) {
  const doc = panel.ownerDocument, win = doc.defaultView;
  const enabled = () => [...panel.querySelectorAll(menu
    ? '[role="menuitem"]:not([disabled]):not([aria-disabled="true"])'
    : 'button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]')]
    .filter(item => !item.closest('[hidden]'));
  const reposition = () => {
    const viewport = win.visualViewport;
    const rect = trigger.getBoundingClientRect();
    const offsetX = viewport?.offsetLeft || 0, offsetY = viewport?.offsetTop || 0;
    const position = positionPanel({ left: rect.left - offsetX, right: rect.right - offsetX,
      top: rect.top - offsetY, bottom: rect.bottom - offsetY },
      { width: panel.offsetWidth, height: panel.scrollHeight },
      { width: viewport?.width ?? win.innerWidth, height: viewport?.height ?? win.innerHeight });
    Object.assign(panel.style, { left: `${position.left + (viewport?.offsetLeft || 0)}px`,
      top: `${position.top + (viewport?.offsetTop || 0)}px`, width: `${position.width}px`,
      maxHeight: `${position.maxHeight}px` });
    panel.dataset.placement = position.placement;
  };
  const dismiss = (restore = false) => { close(); if (restore) trigger.focus(); };
  const outside = event => {
    if (!panel.contains(event.target) && !trigger.contains(event.target)) dismiss();
  };
  let search = "", searchedAt = 0;
  const keydown = event => {
    const target = event.target || doc.activeElement;
    if (!panel.contains(target) && !trigger.contains(target)) return;
    if (event.key === "Escape") {
      event.preventDefault(); event.stopPropagation(); dismiss(true); return;
    }
    if (!menu) return;
    const items = enabled(), index = items.indexOf(doc.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault(); items[nextMenuIndex(index, event.key, items.length)]?.focus();
    } else if (event.key === " " && doc.activeElement?.tagName === "A") {
      event.preventDefault(); doc.activeElement.click();
    } else if (event.key === "Tab") {
      event.preventDefault();
      const page = [...doc.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]')]
        .filter(item => !panel.contains(item) && item.getClientRects().length && !item.closest('[inert]'));
      const next = page[page.indexOf(trigger) + (event.shiftKey ? -1 : 1)];
      dismiss(); (next || trigger).focus();
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey && event.key !== " ") {
      const now = Date.now();
      search = (now - searchedAt < 700 ? search : "") + event.key.toLocaleLowerCase(); searchedAt = now;
      const ordered = [...items.slice(index + 1), ...items.slice(0, index + 1)];
      const match = ordered.find(item => item.textContent.trim().toLocaleLowerCase().startsWith(search));
      if (match) { event.preventDefault(); match.focus(); }
    }
  };
  reposition();
  const items = enabled();
  (initialFocus === "last" ? items.at(-1) : items[0])?.focus();
  if (!items.length) panel.focus();
  doc.addEventListener("pointerdown", outside, true);
  doc.addEventListener("focusin", outside);
  doc.addEventListener("keydown", keydown);
  win.addEventListener("resize", reposition);
  win.addEventListener("scroll", reposition, true);
  win.visualViewport?.addEventListener("resize", reposition);
  const observer = win.ResizeObserver ? new win.ResizeObserver(reposition) : null;
  observer?.observe(panel); observer?.observe(trigger);
  return () => {
    doc.removeEventListener("pointerdown", outside, true);
    doc.removeEventListener("focusin", outside);
    doc.removeEventListener("keydown", keydown);
    win.removeEventListener("resize", reposition);
    win.removeEventListener("scroll", reposition, true);
    win.visualViewport?.removeEventListener("resize", reposition);
    observer?.disconnect();
  };
}
