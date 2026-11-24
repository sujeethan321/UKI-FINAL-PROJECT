// Purpose: Render the reusable dropdown interface and keep its presentation and interactions together.
import { useCallback, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import Popover from "./Popover";

// Render the dropdown interface and connect its controls to the state and callbacks defined here.
export default function Dropdown({ label, trigger, children, className = "", panelClassName = "", disabled = false }) {
  const [open, setOpen] = useState(false), [edge, setEdge] = useState("first");
  const anchor = useRef(null), id = useId();
  const close = useCallback(() => setOpen(false), []);
  return <>
    <button ref={anchor} type="button" disabled={disabled} aria-label={label} aria-haspopup="menu"
      aria-expanded={open} aria-controls={open ? id : undefined} className={`lp-dropdown-trigger ${className}`}
      onClick={() => { setEdge("first"); setOpen(value => !value); }}
      onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) {
          event.preventDefault(); setEdge(event.key === "ArrowUp" ? "last" : "first"); setOpen(true);
        }
      }}>
      {trigger || label}<ChevronDown size={16} className="lp-chevron" aria-hidden="true" />
    </button>
    <Popover open={open} onClose={close} triggerRef={anchor} id={id} label={label} menu
      initialFocus={edge} className={`lp-menu ${panelClassName}`}>{children}</Popover>
  </>;
}
