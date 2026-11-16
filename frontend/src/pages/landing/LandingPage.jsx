import { useState } from "react";
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


function LandingHeader() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

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
        id="landing-navigation"
        className={open ? "landing-nav is-open" : "landing-nav"}
        aria-label={t("aria.navigation")}
        onClick={() => setOpen(false)}
      >
        <a href="#home" aria-current="page">{t("nav.home")}</a>
        <a href="#features">{t("nav.features")}</a>
        <a href="#who-can-use">{t("nav.businesses")}</a>
        <a href="#how-it-works">{t("nav.how")}</a>
        <a href="#why-lankapex">{t("nav.about")}</a>
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


const featureIcons = [CreditCard, ShoppingCart, Truck, BarChart3];
const roleIcons = [Store, UserRound, Truck];
const roleRoutes = ["shop-owner", "customer", "driver"];
const registerKeys = ["hero.registerOwner", "hero.registerCustomer", "hero.registerDriver"];
const benefitIcons = [CreditCard, BarChart3, UsersRound, ShieldCheck];
const detailIcons = [CreditCard, UsersRound, Bell, Bell, ShoppingCart, Truck];
const quickLinks = [["nav.home", "home"], ["nav.features", "features"], ["nav.how", "how-it-works"], ["sections.roles.title", "who-can-use"], ["sections.why.title", "why-lankapex"], ["sections.faq.title", "faq"]];
const translatedItems = (t, key, icons) => icons.map((Icon, index) => ({ ...t(`${key}.${index}`, { returnObjects: true }), Icon }));

function SectionHeading({ id, title, children }) {
  return <div className="landing-section-heading"><h2 id={id}>{title}</h2><p>{children}</p></div>;
}

export function FaqAccordion({ openFaq, onToggle, t = i18n.t.bind(i18n) }) {
  const faqs = t("faqs", { returnObjects: true });
  return (<div className="landing-faq-list">{faqs.map(([question, answer], index) => <div className="landing-faq-item" key={question}>
        <h3><button type="button" id={"faq-question-" + index} aria-expanded={openFaq === index} aria-controls={"faq-answer-" + index} onClick={() => onToggle(index)}>{question}<ChevronDown aria-hidden="true" className={openFaq === index ? "is-expanded" : ""} size={22} /></button></h3>
        <div id={"faq-answer-" + index} role="region" aria-labelledby={"faq-question-" + index} hidden={openFaq !== index}><p>{answer}</p></div>
      </div>)}</div>);
}

export function RoleShowcase({ selectedRole, onSelect, t = i18n.t.bind(i18n) }) {
  const roles = translatedItems(t, "roles", roleIcons).map((role, index) => ({ ...role, route: roleRoutes[index], registrationLabel: t(registerKeys[index]) }));
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

function LandingEnhancements() {
  const { t } = useTranslation();
  const steps = t("steps", { returnObjects: true });
  const benefits = translatedItems(t, "benefits", benefitIcons);
  const detailedFeatures = translatedItems(t, "details", detailIcons).map((item, index) => ({ ...item, planned: index >= 4 }));
  const [openFaq, setOpenFaq] = useState(null);
  const [selectedRole, setSelectedRole] = useState(0);
  return <>
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
    <section id="explore-features" className="landing-extra-section" aria-labelledby="explore-heading">
      <div className="landing-explore-heading">
        <h2 id="explore-heading">{t("sections.explore.prefix")} <span>{t("sections.explore.accent")}</span>{t("sections.explore.suffix") && <> {t("sections.explore.suffix")}</>}</h2>
        <div className="landing-explore-subtitle"><span className="landing-explore-line" aria-hidden="true" /><p>{t("sections.explore.subtitle")}</p></div>
      </div>
      <div className="landing-extra-grid three">{detailedFeatures.map(({ title, Icon, items, planned, note }) => <article className="landing-info-card" key={title}><span className="landing-icon-circle"><Icon aria-hidden="true" /></span><h3>{title}{planned && <> <span className="landing-status">{t("sections.planned")}</span></>}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul>{note && <p className="landing-card-note">{note}</p>}</article>)}</div>
    </section>
    <section id="faq" className="landing-extra-section" aria-labelledby="faq-heading">
      <SectionHeading id="faq-heading" title={t("sections.faq.title")}>{t("sections.faq.subtitle")}</SectionHeading>
      <FaqAccordion t={t} openFaq={openFaq} onToggle={index => setOpenFaq(openFaq === index ? null : index)} />
    </section>
  </>;
}

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

export default function LandingPage() {
  const { t, i18n: activeI18n } = useTranslation();
  const features = translatedItems(t, "features", featureIcons).map((item, index) => ({ ...item, id: index === 0 ? "business-credit" : undefined }));
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

        <section
          className="landing-features"
          id="features"
          aria-label={t("aria.features")}
        >
          <span className="landing-section-note">
            {t("sections.vision")}
          </span>

          <div className="landing-feature-rows">
            {features.map(({ Icon, title, description, id }, index) => (
              <article className="landing-feature-row" key={title} id={id}>
                <div className="landing-feature-copy">
                  <span className="landing-feature-index" aria-hidden="true">0{index + 1}</span>
                  <h2>{title}</h2>
                  <p>{description}</p>
                </div>
                <div className="landing-feature-visual" aria-hidden="true"><div className="landing-feature-orbit"><Icon strokeWidth={1.25} /></div></div>
              </article>
            ))}
          </div>
        </section>

        <LandingEnhancements />
      </main>
      <LandingFooter />
    </div>
  );
}
