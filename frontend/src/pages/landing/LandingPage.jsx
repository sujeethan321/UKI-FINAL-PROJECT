// Purpose: Render the landing page screen and connect its user interactions to shared application state and services.
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import LanguageSelector from "../../components/LanguageSelector";
import {
  ArrowRight,
  BarChart3,
  Bell,
  ChevronDown,
  CreditCard,
  Menu,
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

// Listen for resource-section changes and return cleanup for the subscriber.
function subscribeToSectionChange(onChange) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

// Get active section within the landing page workflow.
const getActiveSection = () => window.location.hash || "#home";
// Get initial section within the landing page workflow.
const getInitialSection = () => "#home";

const landingNavigation = [
  ["home", "nav.home"],
  ["explore-features", "nav.features"],
  ["how-it-works", "nav.how"],
  ["who-can-use", "nav.businesses"],
  ["why-lankapex", "nav.about"],
];

// Render the landing header interface and connect its controls to the state and callbacks defined here.
function LandingHeader() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const menuButton = useRef(null), navigation = useRef(null);
  const activeSection = useSyncExternalStore(subscribeToSectionChange, getActiveSection, getInitialSection);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    if (!open) return;
    const menu = navigation.current, trigger = menuButton.current;
    menu.querySelector('a')?.focus();
    // Dismiss the open panel when the user interacts outside its trigger and content.
    const outside = event => {
      if (!menu.contains(event.target) && !trigger.contains(event.target)) setOpen(false);
    };
    // Handle keyboard interaction for the current menu or popover.
    const keyboard = event => {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.focus(); }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    document.addEventListener('keydown', keyboard);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
      document.removeEventListener('keydown', keyboard);
    };
  }, [open]);

  return (
    <header className="landing-header">
      <Link to="/" className="landing-brand" aria-label={t("aria.home")}>
        <img
          src={logo}
          alt={t("aria.logo")}
          width="300"
          height="100"
        />
      </Link>

      <button
        ref={menuButton}
        className="landing-menu"
        type="button"
        aria-label={t(open ? "aria.closeMenu" : "aria.openMenu")}
        aria-expanded={open}
        aria-controls="landing-navigation"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X /> : <Menu />}
      </button>

      <nav
        ref={navigation}
        id="landing-navigation"
        className={open ? "landing-nav is-open" : "landing-nav"}
        aria-label={t("aria.navigation")}
        onClick={() => setOpen(false)}
      >
        {landingNavigation.map(([id, label]) => (
          <a key={id} href={"#" + id} aria-current={activeSection === "#" + id ? "location" : undefined}>
            {t(label)}
          </a>
        ))}
      </nav>

      <div className="landing-header-actions">
        <LanguageSelector />
        <Link className="landing-button outline" to="/login">{t("nav.login")}</Link>
        <Link className="landing-button primary" to="/register">
          {t("nav.getStarted")}
        </Link>
      </div>
    </header>
  );
}

// Render the role badge interface and connect its controls to the state and callbacks defined here.
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


const roleIcons = [Store, UserRound, Truck];
const roleRoutes = ["shop-owner", "customer", "driver"];
const registerKeys = ["hero.registerOwner", "hero.registerCustomer", "hero.registerDriver"];
const benefitIcons = [CreditCard, BarChart3, UsersRound, ShieldCheck];
const detailIcons = [CreditCard, UsersRound, Bell, Bell, ShoppingCart, Truck];
const quickLinks = [["nav.home", "home"], ["nav.features", "explore-features"], ["nav.how", "how-it-works"], ["sections.roles.title", "who-can-use"], ["sections.why.title", "why-lankapex"], ["sections.faq.title", "faq"]];
// Resolve item labels through the active application language before rendering them.
const translatedItems = (t, key, icons) => icons.map((Icon, index) => ({ ...t(`${key}.${index}`, { returnObjects: true }), Icon }));

// Render the section heading interface and connect its controls to the state and callbacks defined here.
function SectionHeading({ id, title, children }) {
  return <div className="landing-section-heading"><h2 id={id}>{title}</h2><p>{children}</p></div>;
}

// Render the faq accordion interface and connect its controls to the state and callbacks defined here.
export function FaqAccordion({ openFaq, onToggle, t = i18n.t.bind(i18n) }) {
  const faqs = t("faqs", { returnObjects: true });
  return (<div className="landing-faq-list">{faqs.map(([question, answer], index) => <div className="landing-faq-item" key={question}>
        <h3><button type="button" id={"faq-question-" + index} aria-expanded={openFaq === index} aria-controls={"faq-answer-" + index} onClick={() => onToggle(index)}>{question}<ChevronDown aria-hidden="true" className={openFaq === index ? "is-expanded" : ""} size={22} /></button></h3>
        <div id={"faq-answer-" + index} role="region" aria-labelledby={"faq-question-" + index} hidden={openFaq !== index}><p>{answer}</p></div>
      </div>)}</div>);
}

// Render the role showcase interface and connect its controls to the state and callbacks defined here.
export function RoleShowcase({ selectedRole, onSelect, t = i18n.t.bind(i18n) }) {
  const roles = translatedItems(t, "roles", roleIcons).map((role, index) => ({ ...role, route: roleRoutes[index], registrationLabel: t(registerKeys[index]) }));
  // Handle supported keys so the control can be operated without a pointer.
  function onKeyDown(event, index) {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % roles.length;
    else if (event.key === "ArrowLeft") next = (index + roles.length - 1) % roles.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = roles.length - 1;
    else return;
    event.preventDefault();
    onSelect(next);
    event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next].focus();
  }
  return <div className="landing-role-showcase">
    <div className="landing-role-tabs" role="tablist" aria-label={t("aria.accountTypes")}>
      {roles.map(({ title, Icon, route }, index) => <button key={route} type="button" role="tab"
        id={`role-tab-${route}`} aria-controls={`role-panel-${route}`} aria-selected={selectedRole === index}
        tabIndex={selectedRole === index ? 0 : -1} onClick={() => onSelect(index)} onKeyDown={event => onKeyDown(event, index)}>
        <Icon size={22} aria-hidden="true" />{title}
      </button>)}
    </div>
    {roles.map(({ title, Icon, route, description, items, note, registrationLabel }, index) => <article key={route}
      className="landing-role-panel" role="tabpanel" id={`role-panel-${route}`}
      aria-labelledby={`role-tab-${route}`} hidden={selectedRole !== index} tabIndex={0}>
      <div className="landing-role-intro"><Icon size={48} aria-hidden="true" /><h3>{title}</h3><p>{description}</p>
        <Link className="landing-button primary" to={"/register/" + route}>{registrationLabel}<ArrowRight size={18} aria-hidden="true" /></Link>
      </div>
      <div className="landing-role-details"><ul>{items.map(item => <li key={item}>{item}</li>)}</ul>{note && <p>{note}</p>}</div>
    </article>)}
  </div>;
}

// Render the landing enhancements interface and connect its controls to the state and callbacks defined here.
function LandingEnhancements() {
  const { t } = useTranslation();
  const steps = t("steps", { returnObjects: true });
  const benefits = translatedItems(t, "benefits", benefitIcons);
  const detailedFeatures = translatedItems(t, "details", detailIcons).map((item, index) => ({ ...item, planned: index >= 4 }));
  const [openFaq, setOpenFaq] = useState(null);
  const [selectedRole, setSelectedRole] = useState(0);
  return <>
    <section id="explore-features" className="landing-extra-section" aria-labelledby="explore-heading">
      <div className="landing-explore-heading">
        <h2 id="explore-heading">{t("sections.explore.prefix")} <span>{t("sections.explore.accent")}</span>{t("sections.explore.suffix") && <> {t("sections.explore.suffix")}</>}</h2>
        <div className="landing-explore-subtitle"><span className="landing-explore-line" aria-hidden="true" /><p>{t("sections.explore.subtitle")}</p></div>
      </div>
      <div className="landing-extra-grid three">{detailedFeatures.map(({ title, Icon, items, planned, note }) => <article className="landing-info-card" key={title}><span className="landing-icon-circle"><Icon aria-hidden="true" /></span><h3>{title}{planned && <> <span className="landing-status">{t("sections.planned")}</span></>}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul>{note && <p className="landing-card-note">{note}</p>}</article>)}</div>
    </section>
    <section id="how-it-works" className="landing-extra-section" aria-labelledby="how-heading">
      <SectionHeading id="how-heading" title={t("sections.how.title")}>{t("sections.how.subtitle")}</SectionHeading>
      <ol className="landing-timeline">
        {steps.map(([title, description], index) => <li key={title}><span className="landing-timeline-number" aria-hidden="true">{index + 1}</span><div><h3>{title}</h3><p>{description}</p></div></li>)}
      </ol>
    </section>
    <section id="who-can-use" className="landing-extra-section" aria-labelledby="roles-heading">
      <SectionHeading id="roles-heading" title={t("sections.roles.title")}>{t("sections.roles.subtitle")}</SectionHeading>
      <RoleShowcase t={t} selectedRole={selectedRole} onSelect={setSelectedRole} />
    </section>
    <section id="why-lankapex" className="landing-extra-section" aria-labelledby="why-heading">
      <SectionHeading id="why-heading" title={t("sections.why.title")}>{t("sections.why.subtitle")}</SectionHeading>
      <div className="landing-editorial">{benefits.map(({ title, Icon, description }, index) => <article key={title}><div className="landing-editorial-marker"><span aria-hidden="true">0{index + 1}</span><Icon size={26} aria-hidden="true" /></div><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <section id="faq" className="landing-extra-section" aria-labelledby="faq-heading">
      <SectionHeading id="faq-heading" title={t("sections.faq.title")}>{t("sections.faq.subtitle")}</SectionHeading>
      <FaqAccordion t={t} openFaq={openFaq} onToggle={index => setOpenFaq(openFaq === index ? null : index)} />
    </section>
  </>;
}

// Render the landing footer interface and connect its controls to the state and callbacks defined here.
function LandingFooter() {
  const { t } = useTranslation();
  return <footer id="contact" className="landing-footer" aria-label={t("aria.footer")}>
    <div className="landing-footer-grid">
      <div><BrandLogo alt={t("aria.logo")} /><p>{t("footer.description")}</p></div>
      <nav aria-label={t("aria.quickLinks")}><h2>{t("footer.quickLinks")}</h2>{quickLinks.map(([label, id]) => <a href={"#" + id} key={id}>{t(label)}</a>)}</nav>
      <nav aria-label={t("aria.accountLinks")}><h2>{t("footer.accountLinks")}</h2><Link to="/login">{t("nav.login")}</Link><Link to="/register">{t("nav.register")}</Link></nav>
      <div><h2>{t("footer.contact")}</h2><p>{t("footer.contactDetails")}</p></div>
    </div>
    <p className="landing-footer-bottom">{t("footer.copyright", { year: new Date().getFullYear() })}</p>
  </footer>;
}

// Render the landing page interface and connect its controls to the state and callbacks defined here.
export default function LandingPage() {
  const { t, i18n: activeI18n } = useTranslation();
  return (
    <div className="landing-page" id="home" lang={activeI18n.resolvedLanguage || "en"}>
      <LandingHeader />

      <main>
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-photo">
            <img
              src={hero}
              alt={t("aria.heroImage")}
              width="1536"
              height="1024"
              fetchPriority="high"
            />
          </div>

          <div className="landing-hero-copy">
            <p className="landing-eyebrow">{t("hero.eyebrow")}</p>
            <h1 id="landing-title">
              {t("hero.credit")}<br />
              {t("hero.management")}<br />
              {t("hero.and")} <span>{t("hero.delivery")}</span>
            </h1>
            <p className="landing-description">
              {t("hero.description")}
            </p>

            <div className="landing-hero-actions">
              <Link to="/register/shop-owner" className="landing-button registration">
                {t("hero.registerOwner")} <ArrowRight size={20} aria-hidden="true" />
              </Link>
              <Link to="/register/customer" className="landing-button registration">
                {t("hero.registerCustomer")} <ArrowRight size={20} aria-hidden="true" />
              </Link>
              <Link to="/register/driver" className="landing-button registration">
                {t("hero.registerDriver")} <ArrowRight size={20} aria-hidden="true" />
              </Link>
            </div>
          </div>

          <div className="landing-role-overlays">
            <RoleBadge Icon={Store} title={t("hero.shopOwner")} className="owner">
              {t("hero.ownerBadge")}
            </RoleBadge>
            <RoleBadge Icon={UserRound} title={t("hero.customer")} className="customer">
              {t("hero.customerBadge")}
            </RoleBadge>
            <RoleBadge Icon={Truck} title={t("hero.driver")} className="driver">
              {t("hero.driverBadge")}
            </RoleBadge>
            <p className="landing-handwriting" aria-hidden="true">
              {t("hero.business")}<br />
              <span>{t("hero.connects")}</span><br />
              <em>{t("hero.everyone")}</em>
            </p>
          </div>
        </section>

        <LandingEnhancements />
      </main>
      <LandingFooter />
    </div>
  );
}
