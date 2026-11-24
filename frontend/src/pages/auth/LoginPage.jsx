// Purpose: Render the login page screen and connect its user interactions to shared application state and services.
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { loginDestination, validateJoinReturnPath } from "../../utils/joinReturn";


import LoginBrandPanel from "./LoginBrandPanel";
import LoginForm from "./LoginForm";

// Render the login page interface and connect its controls to the state and callbacks defined here.
export default function LoginPage() {
  const { user, loading, isAuthenticated } = useAuth();
  const location = useLocation();
  const joinReturnTo = validateJoinReturnPath(location.state?.joinReturnTo);
  if (!loading && isAuthenticated && user) {
    const destination = loginDestination(user, joinReturnTo);
    if (destination !== "/login") return <Navigate to={destination} replace />;
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
        <LoginBrandPanel />

        <section className="flex items-center justify-center px-5 py-10 sm:px-10 lg:items-start lg:px-8 lg:py-8 xl:px-12">
          <LoginForm joinReturnTo={joinReturnTo} />
        </section>
      </div>
    </main>
  );
}
