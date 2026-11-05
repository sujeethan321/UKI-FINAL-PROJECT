import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Bell,
  ChevronDown,
  CreditCard,
  Globe2,
  Menu,
  Play,
  ShieldCheck,
  ShoppingCart,
  Store,
  Truck,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";

import BrandLogo from "../../components/BrandLogo";
import logo from "../../assets/lankapex-logo.png";
import hero from "../../assets/landing-hero.png";
import "./landing.css";

const features = [
  {
    Icon: CreditCard,
    title: "Digital Credit Management",
    id: "business-credit",
    description:
      "Replace handwritten Nayam with a secure, digital credit system. Manage customer accounts, credit limits and outstanding balances easily.",
  },
  {
    Icon: ShoppingCart,
    title: "Credit Purchases",
    description:
      "Allow customers to shop on credit from your business with owner approval, clear records and real-time balance updates.",
  },
  {
    Icon: Truck,
    title: "Delivery Management",
    description:
      "Book deliveries, track orders in real time and ensure reliable, on-time service for your customers.",
  },
  {
    Icon: BarChart3,
    title: "Reports & Insights",
    description:
      "Get clear statements, transaction history and business insights to make better, faster decisions.",
  },
];

const statistics = [
  {
    Icon: UsersRound,
    value: "500+",
    label: "Local Businesses",
    detail: "Trust LankaPex",
  },
  {
    Icon: UserRound,
    value: "5,000+",
    label: "Customers",
    detail: "Using Digital Credit",
  },
  {
    Icon: Truck,
    value: "300+",
    label: "Delivery Partners",
    detail: "Across Sri Lanka",
  },
  {
    Icon: ShieldCheck,
    value: "99%",
    label: "Reliable & Secure",
    detail: "Transactions",
  },
];

function LandingHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="landing-header">
      <Link to="/" className="landing-brand" aria-label="LankaPex home">
        <img
          src={logo}
          alt="LankaPex — Business Connects Everyone"
          width="300"
          height="100"
        />
      </Link>

      <button
        className="landing-menu"
        type="button"
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        aria-controls="landing-navigation"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X /> : <Menu />}
      </button>

      <nav
        id="landing-navigation"
        className={open ? "landing-nav is-open" : "landing-nav"}
        aria-label="Main navigation"
        onClick={() => setOpen(false)}
      >
        <a href="#home" aria-current="page">Home</a>
        <a href="#features">Features</a>
        <a href="#who-can-use">For Businesses</a>
        <a href="#how-it-works">How It Works</a>
        <a href="#why-lankapex">About Us</a>
      </nav>

      <div className="landing-header-actions">
        <span
          className="landing-language"
          title="English; other translations are not available"
          aria-label="Language: English only"
        >
          <Globe2 size={21} />
          EN
          <ChevronDown size={13} />
        </span>
        <Link className="landing-button outline" to="/login">Log In</Link>
        <Link className="landing-button primary" to="/register">
          Get Started
        </Link>
      </div>
    </header>
  );
}

function RoleBadge({ Icon, title, children, className }) {
  return (
    <div className={`landing-role ${className}`}>
      <span><Icon size={21} aria-hidden="true" /></span>
      <div>
        <strong>{title}</strong>
        <small>{children}</small>
      </div>
    </div>
  );
}


const steps = [
  ["Create Your Account", "Choose Shop Owner, Customer or Delivery Driver when registering."],
  ["Set Up Your Profile", "Complete the information required for your account."],
  ["Use LankaPex", "Shop owners manage credit, customers shop and drivers handle available delivery work as supported. Shopping and delivery workflows are under development."],
  ["Track Your Activity", "View supported records, updates and account information from your dashboard."],
];
const roles = [
  { title: "Shop Owner", Icon: Store, route: "shop-owner", description: "Manage customer accounts, record credit sales and repayments, and keep business records organized.", items: ["Customer credit management", "Repayment records", "Statements and reminders", "Shop and order management (planned)"] },
  { title: "Customer", Icon: UserRound, route: "customer", description: "Connect with local shops, manage credit purchases and view account activity as the customer workflow develops.", items: ["Browse local shops (planned)", "Request credit purchases (planned)", "View account and repayment details (planned)", "Follow customer orders (planned)"], note: "Customer registration and sign-in are available. The customer dashboard currently shows account identity; credit details and commerce tools are planned." },
  { title: "Delivery Driver", Icon: Truck, route: "driver", description: "Connect with businesses that need delivery services and manage delivery work as these tools become available.", items: ["View available delivery requests (planned)", "Accept suitable delivery jobs (planned)", "Update delivery progress (planned)", "View delivery history (planned)"], note: "Driver registration and sign-in are available. Delivery workflows are planned." },
];
const benefits = [
  { title: "Easy Credit Tracking", Icon: CreditCard, description: "Keep credit sales, repayments and outstanding amounts organized." },
  { title: "Less Manual Work", Icon: BarChart3, description: "Reduce dependence on handwritten records and scattered messages." },
  { title: "Connected Services", Icon: UsersRound, description: "Bring customer shopping and delivery coordination together as the platform grows." },
  { title: "Secure Business Records", Icon: ShieldCheck, description: "Protect customer information using authenticated, business-specific access." },
];
const detailedFeatures = [
  { title: "Digital Credit Ledger", Icon: CreditCard, items: ["Record credit sales", "Track customer balances", "Record partial and full repayments", "Maintain ledger history"] },
  { title: "Customer Management", Icon: UsersRound, items: ["Add and update customers", "Manage credit limits", "View customer account details", "Track outstanding balances"] },
  { title: "Payment Reminders", Icon: Bell, items: ["Prepare payment reminders", "View reminder history", "Use supported English and Tamil messages", "Open WhatsApp with a prepared reminder"], note: "WhatsApp click-to-chat does not confirm message delivery. Review and send the message manually; handoff depends on recorded customer permission and eligibility." },
  { title: "Notifications", Icon: Bell, items: ["Receive in-app activity updates", "View notification history", "Track read and unread notifications"] },
  { title: "Shopping and Orders", Icon: ShoppingCart, planned: true, items: ["Browse local shop products", "Place customer orders", "Request credit purchases with shop approval", "Follow order progress"] },
  { title: "Delivery Management", Icon: Truck, planned: true, items: ["Request delivery services", "Connect with available drivers", "Manage deliveries", "Track delivery progress"] },
];
const faqs = [
  ["What is LankaPex?", "LankaPex is a platform designed to help Sri Lankan shops manage digital credit and connect with customers and delivery partners."],
  ["Who can register?", "Shop Owners, Customers and Delivery Drivers can register. Platform Administrators are managed separately."],
  ["Can a Shop Owner manage customer credit?", "Yes. LankaPex supports customer credit accounts, credit sales, repayments and outstanding-balance records."],
  ["Can customers buy products on credit?", "Credit purchasing and customer ordering are part of the planned commerce workflow. Availability depends on the development stage and shop approval."],
  ["Does LankaPex send payment reminders through WhatsApp?", "LankaPex can prepare a reminder and open WhatsApp with a prefilled message. The shop owner must review and send it manually."],
  ["Is LankaPex free?", "Proposed subscription plans include a free starter tier and paid business tiers. Final pricing is not yet confirmed."],
];
const quickLinks = [["Home", "home"], ["Features", "features"], ["How It Works", "how-it-works"], ["Who Can Use LankaPex?", "who-can-use"], ["Why Choose LankaPex?", "why-lankapex"], ["Frequently Asked Questions", "faq"]];

function SectionHeading({ id, title, children }) {
  return <div className="landing-section-heading"><h2 id={id}>{title}</h2><p>{children}</p></div>;
}

export function FaqAccordion({ openFaq, onToggle }) {
  return (<div className="landing-faq-list">{faqs.map(([question, answer], index) => <div className="landing-faq-item" key={question}>
        <h3><button type="button" id={"faq-question-" + index} aria-expanded={openFaq === index} aria-controls={"faq-answer-" + index} onClick={() => onToggle(index)}>{question}<ChevronDown aria-hidden="true" className={openFaq === index ? "is-expanded" : ""} size={22} /></button></h3>
        <div id={"faq-answer-" + index} role="region" aria-labelledby={"faq-question-" + index} hidden={openFaq !== index}><p>{answer}</p></div>
      </div>)}</div>);
}

function LandingEnhancements() {
  const [openFaq, setOpenFaq] = useState(null);
  return <>
    <section id="how-it-works" className="landing-extra-section" aria-labelledby="how-heading">
      <SectionHeading id="how-heading" title="How LankaPex Works">Simple steps to connect shops, customers and delivery partners.</SectionHeading>
      <ol className="landing-extra-grid four landing-steps">
        {steps.map(([title, description], index) => <li className="landing-info-card" key={title}><span className="landing-step-number" aria-hidden="true">{index + 1}</span><h3>{title}</h3><p>{description}</p></li>)}
      </ol>
    </section>
    <section id="who-can-use" className="landing-extra-section" aria-labelledby="roles-heading">
      <SectionHeading id="roles-heading" title="Who Can Use LankaPex?">One platform designed for different everyday needs.</SectionHeading>
      <div className="landing-extra-grid three">
        {roles.map(({ title, Icon, route, description, items, note }) => <article className="landing-info-card landing-role-card" key={route}>
          <span className="landing-icon-circle"><Icon aria-hidden="true" /></span><h3>{title}</h3><p>{description}</p><ul>{items.map(item => <li key={item}>{item}</li>)}</ul>{note && <p className="landing-card-note">{note}</p>}
          <Link className="landing-button outline" to={"/register/" + route}>Register as {title}<ArrowRight size={18} aria-hidden="true" /></Link>
        </article>)}
      </div>
    </section>
    <section id="why-lankapex" className="landing-extra-section" aria-labelledby="why-heading">
      <SectionHeading id="why-heading" title="Why Choose LankaPex?">Built to simplify everyday business activities.</SectionHeading>
      <div className="landing-extra-grid four">{benefits.map(({ title, Icon, description }) => <article className="landing-info-card" key={title}><span className="landing-icon-circle"><Icon aria-hidden="true" /></span><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <section id="explore-features" className="landing-extra-section" aria-labelledby="explore-heading">
      <SectionHeading id="explore-heading" title="Explore LankaPex Features">Tools for managing credit today and connecting more business activities in the future.</SectionHeading>
      <div className="landing-extra-grid three">{detailedFeatures.map(({ title, Icon, items, planned, note }) => <article className="landing-info-card" key={title}><span className="landing-icon-circle"><Icon aria-hidden="true" /></span><h3>{title}{planned && <> <span className="landing-status">Planned</span></>}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul>{note && <p className="landing-card-note">{note}</p>}</article>)}</div>
    </section>
    <section id="faq" className="landing-extra-section" aria-labelledby="faq-heading">
      <SectionHeading id="faq-heading" title="Frequently Asked Questions">Answers to common questions about LankaPex.</SectionHeading>
      <FaqAccordion openFaq={openFaq} onToggle={index => setOpenFaq(openFaq === index ? null : index)} />
    </section>
  </>;
}

function LandingFooter() {
  return <footer id="contact" className="landing-footer" aria-label="Contact and footer">
    <div className="landing-footer-grid">
      <div><BrandLogo /><p>Connecting Sri Lankan businesses, customers and delivery partners through digital credit and connected services.</p></div>
      <nav aria-label="Footer quick links"><h2>Quick Links</h2>{quickLinks.map(([label, id]) => <a href={"#" + id} key={id}>{label}</a>)}</nav>
      <nav aria-label="Footer account links"><h2>Account Links</h2><Link to="/login">Log In</Link><Link to="/register">Register</Link></nav>
      <div><h2>Contact</h2><p>Contact details coming soon</p></div>
    </div>
    <p className="landing-footer-bottom">© {new Date().getFullYear()} LankaPex — Business Connects Everyone</p>
  </footer>;
}

export default function LandingPage() {
  return (
    <div className="landing-page" id="home">
      <LandingHeader />

      <main>
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-photo">
            <img
              src={hero}
              alt="Sri Lankan shop owner using a tablet, customer using a smartphone, and motorcycle delivery partner beside a town lake"
              width="1536"
              height="1024"
              fetchPriority="high"
            />
          </div>

          <div className="landing-hero-copy">
            <p className="landing-eyebrow">WELCOME TO LANKAPEX</p>
            <h1 id="landing-title">
              Digital Credit<br />
              Management<br />
              &amp; <span>Delivery Platform</span>
            </h1>
            <p className="landing-description">
              Connects Sri Lankan businesses, customers and delivery partners
              with a simple and powerful digital platform.
            </p>

            <div className="landing-hero-icons" aria-label="Platform capabilities">
              {features.map(({ Icon, title }) => (
                <span
                  className="landing-icon-tile"
                  key={title}
                  role="img"
                  aria-label={title}
                >
                  <Icon aria-hidden="true" />
                </span>
              ))}
            </div>

            <div className="landing-hero-actions">
              <Link to="/login" className="landing-button primary">
                Log In <ArrowRight size={24} />
              </Link>
              <a href="#features" className="landing-button outline">
                <span className="landing-play">
                  <Play size={13} fill="currentColor" />
                </span>
                Learn More
              </a>
            </div>
          </div>

          <div className="landing-role-overlays">
            <RoleBadge Icon={Store} title="Shop Owner" className="owner">
              Manage Credit &amp; Orders
            </RoleBadge>
            <RoleBadge Icon={UserRound} title="Customer" className="customer">
              Shop on Credit
            </RoleBadge>
            <RoleBadge Icon={Truck} title="Delivery Driver" className="driver">
              Earn with Deliveries
            </RoleBadge>
            <p className="landing-handwriting" aria-hidden="true">
              Business<br />
              <span>Connects</span><br />
              <em>Everyone</em>
            </p>
          </div>
        </section>

        <section
          className="landing-features"
          id="features"
          aria-label="Planned platform features"
        >
          <span className="landing-section-note">
            Platform vision · capabilities are being developed
          </span>

          <div className="landing-feature-grid">
            {features.map(({ Icon, title, description, id }) => (
              <article key={title} id={id}>
                <span className="landing-icon-circle">
                  <Icon aria-hidden="true" />
                </span>
                <div>
                  <h2>{title}</h2>
                  <p>{description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-statistics" aria-label="Illustrative platform figures">
          <div className="landing-stat-grid">
            {statistics.map(({ Icon, value, label, detail }) => (
              <div className="landing-stat" key={label}>
                <span className="landing-icon-circle">
                  <Icon aria-hidden="true" />
                </span>
                <div>
                  <strong>{value}</strong>
                  <h2>{label}</h2>
                  <p>{detail}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="landing-stat-note">Illustrative platform figures — not verified adoption or security metrics.</p>
        </section>
        <LandingEnhancements />
      </main>
      <LandingFooter />
    </div>
  );
}
