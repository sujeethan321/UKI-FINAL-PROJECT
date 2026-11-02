
import { Link } from "react-router-dom";
import { Store, ArrowRight } from "lucide-react";

export default function AdminDashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-[#10243E]">
          Platform Overview
        </h2>
        <p className="mt-2 text-sm text-[#64748B]">
          Manage LankaPex platform operations.
        </p>
      </div>

      <Link
        to="/admin/businesses"
        className="flex max-w-md items-center justify-between rounded-2xl border border-[#D4E2EE] bg-white p-6 transition hover:border-[#12B8A6]"
      >
        <div className="flex items-center gap-4">
          <span className="rounded-xl bg-[#E8F8F6] p-3 text-[#0AAE9F]">
            <Store size={24} />
          </span>

          <div>
            <h3 className="font-semibold text-[#10243E]">
              Business Management
            </h3>
            <p className="mt-1 text-sm text-[#64748B]">
              Review business applications
            </p>
          </div>
        </div>

        <ArrowRight size={20} className="text-[#12B8A6]" />
      </Link>
    </div>
  );
}
