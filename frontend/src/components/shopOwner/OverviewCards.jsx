import { useAppTranslation } from "../../i18n/useAppTranslation.js";

import {
  Wallet,
  HandCoins,
  AlertTriangle,
} from "lucide-react";

const cardDefinitions = [
  {
    key: "total_outstanding",
    title: "Total Outstanding",
    icon: Wallet,
    type: "currency",
  },
  {
    key: "collected_today",
    title: "Collected Today",
    icon: HandCoins,
    type: "currency",
  },
  {
    key: "overdue_amount",
    title: "Overdue Amount",
    icon: AlertTriangle,
    type: "currency",
    danger: true,
  },

];

function formatValue(value, type) {
  // Null/undefined means data is unavailable.
  // Zero is a valid value and should display as 0.
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  if (type === "currency") {
    return `LKR ${number.toLocaleString("en-LK", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    })}`;
  }

  return number.toLocaleString("en-LK");
}

export default function OverviewCards({ summary = null }) {
  const { tr } = useAppTranslation();
  return (
    <section aria-labelledby="overview-heading">
      <div className="sr-only">
        <h2
          id="overview-heading"
          className="text-xl font-bold text-[#10243E]"
        >{tr("Business Overview")}</h2>

        <p className="mt-1 text-sm text-[#64748B]">{tr("Your shop's credit and delivery activity at a glance.")}</p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {cardDefinitions.map((card) => {
          const Icon = card.icon;
          const value = summary?.[card.key];
          const hasData =
            value !== null &&
            value !== undefined &&
            value !== "" &&
            Number.isFinite(Number(value));

          return (
            <article
              key={card.key}
              className="min-h-[145px] rounded-2xl border border-[#D4E2EE] bg-white p-6 shadow-[0_3px_12px_rgba(16,36,62,0.025)]"
            >
              <div className="flex flex-row-reverse items-center justify-end gap-4">
                <h3 className="text-base font-semibold text-[#10243E]">
                  {tr(card.title)}
                </h3>

                <span
                  className={
                    card.danger
                      ? "rounded-xl bg-red-50 p-4 text-red-500"
                      : "rounded-xl bg-[#E8F8F6] p-4 text-[#0AAE9F]"
                  }
                >
                  <Icon size={20} aria-hidden="true" />
                </span>
              </div>

              <p
                className={`mt-5 text-2xl font-bold tracking-tight sm:text-3xl ${
                  card.danger
                    ? "text-[#DC4545]"
                    : "text-[#10243E]"
                }`}
              >
                {formatValue(value, card.type)}
              </p>

              {!hasData && (
                <p className="mt-2 text-xs text-[#64748B]">{tr("Data not connected yet")}</p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
