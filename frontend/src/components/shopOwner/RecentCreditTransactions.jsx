import { useAppTranslation } from "../../i18n/useAppTranslation.js";

import { ReceiptText } from "lucide-react";

function formatAmount(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const amount = Number(value);

  if (!Number.isFinite(amount)) {
    return "—";
  }

  return `LKR ${amount.toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function RecentCreditTransactions({
  transactions = null,
}) {
  const { tr } = useAppTranslation();
  // null means the API hasn't been connected.
  // [] means the API loaded successfully but found no records.
  const isConnected = Array.isArray(transactions);

  const recentTransactions = isConnected
    ? transactions.slice(0, 5)
    : [];

  return (
    <section
      aria-labelledby="recent-transactions-title"
      className="min-h-[320px] rounded-2xl border border-[#D4E2EE] bg-white p-6"
    >
      <h2
        id="recent-transactions-title"
        className="text-lg font-semibold text-[#10243E]"
      >{tr("Recent Activity")}</h2>

      {!isConnected ? (
        <div className="flex min-h-[230px] flex-col items-center justify-center gap-3 text-center">
          <ReceiptText
            size={34}
            className="text-[#9AAFC1]"
            aria-hidden="true"
          />

          <p className="font-medium text-[#10243E]">{tr("Transaction data not connected yet")}</p>

          <p className="max-w-xs text-sm text-[#64748B]">{tr("Your latest credit sales and repayments will appear here after the ledger API is connected.")}</p>
        </div>
      ) : recentTransactions.length === 0 ? (
        <div className="flex min-h-[230px] flex-col items-center justify-center text-center">
          <ReceiptText
            size={34}
            className="mb-3 text-[#9AAFC1]"
          />

          <p className="font-medium text-[#10243E]">{tr("No recent transactions")}</p>

          <p className="mt-2 text-sm text-[#64748B]">{tr("Transactions will appear here when available.")}</p>
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left">
            <thead>
              <tr className="border-b border-[#E2EAF2] text-sm text-[#64748B]">
                <th className="pb-3 font-medium">{tr("Customer")}</th>
                <th className="pb-3 font-medium">{tr("Transaction")}</th>
                <th className="pb-3 text-right font-medium">{tr("Amount")}</th>
              </tr>
            </thead>

            <tbody>
              {recentTransactions.map((transaction) => (
                <tr
                  key={transaction.id}
                  className="border-b border-[#F0F4F8] last:border-0"
                >
                  <td className="py-4 text-sm font-medium text-[#10243E]">
                    {transaction.customer_name || tr("Unknown customer")}
                  </td>

                  <td className="py-4 text-sm text-[#64748B]">
                    {transaction.type === "credit_sale"
                      ? tr("Credit sale")
                      : transaction.type === "repayment"
                        ? tr("Repayment")
                        : transaction.type || tr("Other")}
                  </td>

                  <td className={"py-4 text-right text-sm font-semibold " + (transaction.type === "repayment" ? "text-[#16A566]" : "text-[#10243E]")}>
                    {formatAmount(transaction.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
