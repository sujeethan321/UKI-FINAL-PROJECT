
import { Navigate, useParams } from "react-router-dom";

import LoginBrandPanel from "./LoginBrandPanel";
import LoginForm from "./LoginForm";

const allowedRoles = [
  "shop-owner",
  "customer",
  "driver",
  "admin",
];

export default function LoginPage() {
  const { role } = useParams();

  if (!allowedRoles.includes(role)) {
    return <Navigate to="/select-role" replace />;
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#F8FCFF] via-[#EAF8FF] to-[#D8F0FF] font-sans">
      {/* Background decorative shapes */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-56 left-[40%] h-[580px] w-[580px] rounded-full border-[85px] border-[#0ABCC1]/20"
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-56 -right-32 h-[650px] w-[650px] rounded-full bg-gradient-to-br from-[#13D4D5]/35 to-[#028DC4]/30 blur-2xl"
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute right-[35%] top-[35%] h-40 w-40 rounded-full border-2 border-white/70 bg-sky-200/20"
      />

      <div className="relative z-10 grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <LoginBrandPanel role={role} />

        <section className="flex items-center justify-center px-5 py-10 sm:px-10 lg:px-8 xl:px-12">
          <LoginForm key={role} role={role} />
        </section>
      </div>
    </main>
  );
}
