// Purpose: Render the reusable customer data interface and keep its presentation and interactions together.
import { LoaderCircle } from "lucide-react";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";

export const customerButton = "inline-flex items-center justify-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50";
export const customerCard = "min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6";
// Render the customer data state interface and connect its controls to the state and callbacks defined here.
export function CustomerDataState({ state, retry, label, children }) {
  const { tr } = useAppTranslation();
  if (state.loading) return <p role="status" className="flex items-center gap-2 py-6 text-sm text-[#64748B]"><LoaderCircle size={18} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />{tr("Loading {{section}}...", { section: tr(label) })}</p>;
  if (state.error) return <div role="alert" className="my-4 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm text-[#10243E]"><p>{tr(state.error)}</p>{![401, 403, 404, 422].includes(state.status) && <button type="button" className={customerButton} onClick={retry}>{tr("Retry {{section}}", { section: tr(label) })}</button>}</div>;
  return state.data ? children : <p className="py-4 text-sm text-[#64748B]">{tr("Data unavailable.")}</p>;
}
// Render the customer pagination interface and connect its controls to the state and callbacks defined here.
export function CustomerPagination({ page, total, loading, onPage }) {
  const { tr } = useAppTranslation();
  return <div className="mt-5 flex flex-wrap items-center justify-end gap-3 text-sm"><button type="button" className={customerButton} disabled={loading || page <= 1} onClick={() => onPage(page - 1)}>{tr("Previous")}</button><span>{tr("Page")} {page}{total !== null ? tr(" · {{total}} records", { total }) : ""}</span><button type="button" className={customerButton} disabled={loading || total === null || page * 10 >= total} onClick={() => onPage(page + 1)}>{tr("Next")}</button></div>;
}
