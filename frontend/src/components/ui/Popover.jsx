import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { bindFloatingPanel } from "../../utils/floatingPanel";
import "./dropdown.css";

export default function Popover({ open, onClose, triggerRef, id, label, menu = false,
  initialFocus = "first", className = "", children }) {
  const panel = useRef(null);
  useEffect(() => {
    if (!open || !panel.current || !triggerRef.current) return;
    const element = panel.current;
    element.showPopover?.();
    const unbind = bindFloatingPanel({ panel: element, trigger: triggerRef.current,
      close: onClose, menu, initialFocus });
    return () => { unbind(); if (element.hidePopover && element.matches(':popover-open')) element.hidePopover(); };
  }, [open, onClose, triggerRef, menu, initialFocus]);
  if (!open) return null;
  const content = <div ref={panel} id={id} popover="manual" role={menu ? "menu" : "dialog"}
    aria-label={label} tabIndex={-1} className={`lp-popover ${className}`}
    onToggle={event => { if (event.nativeEvent.newState === "closed") onClose(); }}
    onClick={event => {
      if (menu && event.target.closest('a[href],button:not([disabled])')) onClose();
    }}>
    {children}
  </div>;
  // Native top-layer content stays in its original (possibly modal) subtree.
  // Older browsers use a body portal to escape overflowing cards/tables.
  const nativePopover = typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
  return nativePopover || typeof document === "undefined" ? content : createPortal(content, document.body);
}
