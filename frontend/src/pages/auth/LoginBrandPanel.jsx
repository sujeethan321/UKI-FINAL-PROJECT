import LanguageSelector from "../../components/LanguageSelector";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import BrandLogo from "../../components/BrandLogo";

import {
  Users,
  ReceiptText,
  Truck,
  ChartNoAxesColumnIncreasing,
  ShoppingBag,
  CreditCard,
  ShieldCheck,
  Package,
} from "lucide-react";

const contentByRole = {
  "shop-owner": {
    label: "FOR SHOP OWNERS",
    title: "Manage Your Business Smarter",
    highlight: "with Digital Credit",
    description:
      "A simple and powerful platform to manage customers, credit sales, repayments and deliveries — all in one place.",
    features: [
      {
        title: "Customer Management",
        description: "Maintain accurate ledgers and outstanding balances.",
        icon: Users,
        color: "teal",
      },
      {
        title: "Credit Sales & Repayments",
        description: "Track transactions and generate receipts instantly.",
        icon: ReceiptText,
        color: "amber",
      },
      {
        title: "Delivery Management",
        description: "Request deliveries and track their progress.",
        icon: Truck,
        color: "blue",
      },
      {
        title: "Reports & Insights",
        description: "View statements and business performance.",
        icon: ChartNoAxesColumnIncreasing,
        color: "purple",
      },
    ],
  },

  customer: {
    label: "FOR CUSTOMERS",
    title: "Shop Local,",
    highlight: "Stay Connected",
    description:
      "Discover local shops, manage your credit purchases and keep track of orders and repayments.",
    features: [
      {
        title: "Discover Shops",
        description: "Find businesses and products near you.",
        icon: ShoppingBag,
        color: "teal",
      },
      {
        title: "Digital Credit",
        description: "Keep track of your credit purchases.",
        icon: CreditCard,
        color: "amber",
      },
      {
        title: "Order Tracking",
        description: "Follow your orders and deliveries.",
        icon: Package,
        color: "blue",
      },
      {
        title: "Secure Records",
        description: "Access your purchase and repayment history.",
        icon: ShieldCheck,
        color: "purple",
      },
    ],
  },

  driver: {
    label: "FOR DELIVERY PARTNERS",
    title: "Deliver More,",
    highlight: "Earn Smarter",
    description:
      "Connect with shops and customers, manage deliveries and grow your delivery business.",
    features: [
      {
        title: "Delivery Requests",
        description: "Explore available delivery opportunities.",
        icon: Package,
        color: "teal",
      },
      {
        title: "Flexible Work",
        description: "Manage your delivery availability.",
        icon: Truck,
        color: "amber",
      },
      {
        title: "Delivery Updates",
        description: "Track pickup and delivery progress.",
        icon: ReceiptText,
        color: "blue",
      },
      {
        title: "Trusted Platform",
        description: "Connect with participating businesses.",
        icon: ShieldCheck,
        color: "purple",
      },
    ],
  },

  admin: {
    label: "PLATFORM ADMINISTRATION",
    title: "Manage LankaPex",
    highlight: "With Confidence",
    description:
      "Oversee platform users, participating businesses and delivery partners.",
    features: [
      {
        title: "User Management",
        description: "Manage registered platform accounts.",
        icon: Users,
        color: "teal",
      },
      {
        title: "Business Oversight",
        description: "Review participating businesses.",
        icon: ShoppingBag,
        color: "amber",
      },
      {
        title: "Delivery Partners",
        description: "Manage delivery partner records.",
        icon: Truck,
        color: "blue",
      },
      {
        title: "Platform Reports",
        description: "Review operational activity.",
        icon: ChartNoAxesColumnIncreasing,
        color: "purple",
      },
    ],
  },
};

const iconColors = {
  teal: "bg-teal-100 text-teal-600",
  amber: "bg-amber-100 text-amber-500",
  blue: "bg-blue-100 text-blue-600",
  purple: "bg-purple-100 text-purple-600",
};

export function LankaPexLogo() {
  return <BrandLogo />;
}

export default function LoginBrandPanel({ role, registration = false }) {
  const { tr } = useAppTranslation();
  const content =
    contentByRole[role] ?? {
      ...contentByRole["shop-owner"],
      label: "BUSINESS CONNECTS EVERYONE",
      title: "Welcome to LankaPex",
      highlight: "Connect with Confidence",
      description: "Sign in to access your shop owner, customer, delivery driver or administrator account.",
    };

  return (
    <section className={`relative flex flex-col px-6 py-8 sm:px-10 lg:min-h-screen lg:px-12 xl:px-20 ${registration ? "gap-6" : "justify-between gap-10"}`}>
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
        <LankaPexLogo /><LanguageSelector />
      </div>

      <div className="relative z-10 max-w-2xl">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-teal-100/80 px-5 py-2 text-xs font-bold tracking-[0.2em] text-[#10243E]">
          <ShoppingBag size={17} className="text-[#12B8A6]" />
          {tr(content.label)}
        </div>

        <h1 className="text-3xl font-extrabold leading-[1.12] tracking-tight text-[#10243E] sm:text-4xl xl:text-5xl">
          {tr(content.title)}
          <span className="mt-2 block text-[#079D9D]">
            {tr(content.highlight)}
          </span>
        </h1>

        <p className="mt-4 max-w-xl text-base leading-7 text-[#566B8E] sm:text-lg">
          {tr(content.description)}
        </p>

        <div className="mt-7 grid gap-4 sm:grid-cols-2">
          {content.features.map((feature) => {
            const Icon = feature.icon;

            return (
              <div
                key={feature.title}
                className="flex gap-4 rounded-2xl border border-white/75 bg-white/65 p-4 shadow-sm backdrop-blur-lg"
              >
                <div
                  className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${iconColors[feature.color]}`}
                >
                  <Icon size={25} />
                </div>

                <div>
                  <h3 className="text-sm font-bold text-[#10243E]">
                    {tr(feature.title)}
                  </h3>
                  <p className="mt-1 text-sm leading-5 text-[#566B8E]">
                    {tr(feature.description)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className={`relative z-10 text-xs text-[#64748B] ${registration ? "mt-auto pt-6" : ""}`}>{tr("© LankaPex — Business Connects Everyone")}</p>
    </section>
  );
}
