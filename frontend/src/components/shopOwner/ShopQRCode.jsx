// Purpose: Render the reusable shop qr code interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getOrCreateBusinessJoinLink } from "../../services/shopOwnerJoinService";
import { validateJoinReturnPath } from "../../utils/joinReturn";

/* eslint-disable react-refresh/only-export-components -- Exported helpers are covered by focused tests. */

// Build a shop-join URL from the validated public join code.
export function joinUrlForCode(origin, publicCode) {
  const path = validateJoinReturnPath(`/join/${publicCode}`);
  if (!path) return null;
  try {
    const url = new URL(origin);
    if (url.origin !== origin || !["https:", "http:"].includes(url.protocol) || url.username || url.password) return null;
    return `${url.origin}${path}`;
  } catch { return null; }
}

// Translate qr outcomes into display text for the interface.
export function qrError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session expired. Sign in again.";
  if (status === 403) return "Only an approved business owner can access this shop QR code.";
  if (status === 404) return "This business is unavailable to your account.";
  if (status === 409) return "The QR link could not be prepared. Please retry.";
  return "Shop QR code is unavailable. Check your connection and retry.";
}

// Render the shop qr code interface and connect its controls to the state and callbacks defined here.
export default function ShopQRCode({ businessId, businessName }) {
  const { tr } = useAppTranslation();
  const [code, setCode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retry, setRetry] = useState(0);
  const qrRef = useRef(null);
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const url = code ? joinUrlForCode(origin, code) : null;

  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    let active = true;
    getOrCreateBusinessJoinLink(businessId).then(data => {
      if (!active) return;
      if (!validateJoinReturnPath(`/join/${data?.public_code}`)) throw new Error("Invalid QR code response");
      setCode(data.public_code);
      setError("");
    }).catch(err => {
      if (active) { setCode(null); setError(qrError(err)); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [businessId, retry]);

  // Retry the QR resource read after an earlier load failed.
  function retryLoad() { setLoading(true); setNotice(""); setRetry(value => value + 1); }
  // Copy the displayed shop-join URL to the clipboard and report the result.
  async function copy() {
    try { await navigator.clipboard.writeText(url); setNotice("Join link copied."); }
    catch { setNotice("Copy unavailable. Select the link below to copy it."); }
  }
  // Share the current shop-join URL using the browser sharing flow.
  async function share() {
    if (navigator.share) {
      try { await navigator.share({ title: tr("Join {{business}} on LankaPex", { business: businessName }), url }); setNotice("Share sheet opened."); return; }
      catch (error) { if (error?.name === "AbortError") return; }
    }
    await copy();
  }
  // Serialize the QR SVG into text suitable for the download flow.
  function svgText() {
    const svg = qrRef.current?.querySelector("svg");
    if (!svg) return null;
    const copy = svg.cloneNode(true);
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    return new XMLSerializer().serializeToString(copy);
  }
  // Download the current QR asset using the browser download flow.
  function download() {
    const svg = svgText();
    if (!svg) { setNotice("QR download unavailable. Please retry."); return; }
    const objectUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = "lankapex-shop-qr.svg";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }
  // Prepare the current QR view for browser printing.
  function print() {
    const svg = qrRef.current?.querySelector("svg");
    const popup = window.open("", "_blank");
    if (!svg || !popup) { popup?.close(); setNotice("Print unavailable. Please allow pop-ups and retry."); return; }
    popup.document.write("<!doctype html><html><head><title>LankaPex Shop QR</title><style>body{font:16px Arial,sans-serif;text-align:center;padding:2rem;color:#10243e}svg{width:280px;height:280px}p{overflow-wrap:anywhere}</style></head><body></body></html>");
    const heading = popup.document.createElement("h1"); heading.textContent = businessName;
    const caption = popup.document.createElement("p"); caption.textContent = url;
    popup.document.body.append(heading, popup.document.importNode(svg, true), caption);
    popup.document.close(); popup.focus(); popup.print();
  }

  return <section aria-label={tr("Shop QR Code")} className="rounded-xl border border-[#E1EAF4] bg-white p-5 shadow-sm">
    <h3 className="text-lg font-bold text-[#0D1D47]">{tr("Shop QR Code")}</h3>
    <p className="mt-1 text-sm text-[#587098]">{tr("Customers can scan this permanent code to request a connection. Approval does not grant credit.")}</p>
    {loading ? <p role="status" className="mt-4 text-sm">{tr("Loading QR code...")}</p> : error || !url ? <div className="mt-4"><p role="alert" className="text-sm text-red-700">{tr(error || "A valid shop link is unavailable.")}</p><button type="button" onClick={retryLoad} className="mt-3 rounded-lg border border-[#12B8A6] px-4 py-2 text-sm font-semibold text-[#0D1D47]">{tr("Retry")}</button></div> : <>
      <div ref={qrRef} className="mt-5 inline-block rounded-xl border border-[#DAE5F3] bg-white p-4"><QRCodeSVG value={url} size={224} level="M" marginSize={4} fgColor="#10243E" bgColor="#FFFFFF" title={tr("Join {{business}} on LankaPex", { business: businessName })} /></div>
      <p className="mt-2 break-all text-xs text-[#36517B]"><a href={url} target="_blank" rel="noreferrer">{url}</a></p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={copy} className="rounded-lg border border-[#12B8A6] px-3 py-2 text-sm font-semibold text-[#0D1D47] hover:bg-[#E7F9F6]">{tr("Copy Link")}</button>
        <button type="button" onClick={share} className="rounded-lg border border-[#12B8A6] px-3 py-2 text-sm font-semibold text-[#0D1D47] hover:bg-[#E7F9F6]">{tr("Share")}</button>
        <button type="button" onClick={download} className="rounded-lg border border-[#12B8A6] px-3 py-2 text-sm font-semibold text-[#0D1D47] hover:bg-[#E7F9F6]">{tr("Download SVG")}</button>
        <button type="button" onClick={print} className="rounded-lg border border-[#12B8A6] px-3 py-2 text-sm font-semibold text-[#0D1D47] hover:bg-[#E7F9F6]">{tr("Print QR")}</button>
      </div>
      {notice && <p role="status" className="mt-3 text-sm text-[#36517B]">{tr(notice)}</p>}
    </>}
  </section>;
}
