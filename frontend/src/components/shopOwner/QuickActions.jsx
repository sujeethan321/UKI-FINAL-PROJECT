
import {
  CreditCard,
  UserRoundPlus,
  PackagePlus,
  Truck,
  LockKeyhole,
} from "lucide-react";

const actions = [
  {
    id: "credit-sale",
    label: "Record Credit Sale",
    icon: CreditCard,
  },
  {
    id: "add-customer",
    label: "Add Credit Customer",
    icon: UserRoundPlus,
  },
  {
    id: "add-product",
    label: "Add Product",
    icon: PackagePlus,
  },
  {
    id: "book-delivery",
    label: "Book Delivery",
    icon: Truck,
  },
];

export default function QuickActions() {
  return (
    <section
      aria-labelledby="quick-actions-title"
      className="min-h-[320px] rounded-2xl border border-[#D4E2EE] bg-white p-6"
    >
      <h2
        id="quick-actions-title"
        className="text-lg font-semibold text-[#10243E]"
      >
        Quick Actions
      </h2>

      <p className="mt-2 text-sm text-[#64748B]">
        Frequently used shop operations.
      </p>

      <div className="mt-6 space-y-3">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <div
              key={action.id}
              className="flex items-center gap-3 rounded-xl border border-[#E5EDF4] bg-[#F8FAFC] px-4 py-3"
              aria-disabled="true"
              title={`${action.label} — coming soon`}
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#E8F8F6] text-[#0AAE9F]">
                <Icon size={18} aria-hidden="true" />
              </span>

              <span className="flex-1 text-sm font-medium text-[#64748B]">
                {action.label}
              </span>

              <LockKeyhole
                size={15}
                className="text-[#94A3B8]"
                aria-hidden="true"
              />
            </div>
          );
        })}
      </div>

      <p className="mt-5 text-xs text-[#64748B]">
        These actions will be enabled as their features
        and backend services are completed.
      </p>
    </section>
  );
}
