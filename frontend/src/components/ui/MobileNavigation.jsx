import { useEffect, useRef } from "react";
import "./dropdown.css";

export default function MobileNavigation({ open, onClose, id, label, children }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);
  useEffect(() => {
    const desktop = window.matchMedia('(min-width:1024px)');
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
