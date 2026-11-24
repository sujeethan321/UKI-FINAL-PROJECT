// Purpose: Render the reusable mobile navigation interface and keep its presentation and interactions together.
import { useEffect, useRef } from "react";
import "./dropdown.css";

// Render the mobile navigation interface and connect its controls to the state and callbacks defined here.
export default function MobileNavigation({ open, onClose, id, label, children }) {
  const dialog = useRef(null);
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    const element = dialog.current;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    const desktop = window.matchMedia('(min-width:1024px)');
    // Update mobile navigation state when the viewport changes.
    const resize = event => { if (event.matches) onClose(); };
    desktop.addEventListener('change', resize);
    return () => desktop.removeEventListener('change', resize);
  }, [onClose]);
  return <dialog ref={dialog} id={id} aria-label={label} className="lp-mobile-navigation"
    onClose={onClose} onCancel={onClose} onClick={event => {
      if (event.target !== event.currentTarget) return;
      const box = event.currentTarget.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) onClose();
    }}>
    {children}
  </dialog>;
}
