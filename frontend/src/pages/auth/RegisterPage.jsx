// Purpose: Render the register page screen and connect its user interactions to shared application state and services.

import { useEffect, useState, useSyncExternalStore } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { registerShopOwner, registerCustomer, registerDriver } from "../../services/authService";
import { createRegistrationController, publicRegistrationRoles } from "../../utils/registration";
import { getApiErrorMessage } from "../../utils/apiError";
import { registrationLoginState, validateJoinReturnPath } from "../../utils/joinReturn";

import RegistrationForm from "./RegistrationForm";
import LoginBrandPanel from "./LoginBrandPanel";



// Render the register page interface and connect its controls to the state and callbacks defined here.
export default function RegisterPage() {
  const { role = "shop-owner" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const joinReturnTo = validateJoinReturnPath(location.state?.joinReturnTo);
  const [controller] = useState(() => createRegistrationController({
    role,
    services: { "shop-owner": registerShopOwner, customer: registerCustomer, driver: registerDriver },
    errorMessage: getApiErrorMessage,
    // Apply the confirmed operation result to the calling screen state.
    onSuccess: () => {
      const state = registrationLoginState(role, joinReturnTo);
      if (state.joinReturnTo) navigate("/login", { replace: true, state });
      else navigate("/login", { replace: true, state: { registrationSuccess: true } });
    },
  }));
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => {
    controller.resetRole(role);
    return () => controller.cancel();
  }, [controller, role]);
  if (!publicRegistrationRoles.includes(role)) return <Navigate to="/register" replace />;

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#F8FCFF] via-[#EAF8FF] to-[#D8F0FF] font-sans">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-56 left-[40%] h-[580px] w-[580px] rounded-full border-[85px] border-[#0ABCC1]/20"
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-56 -right-32 h-[650px] w-[650px] rounded-full bg-gradient-to-br from-[#13D4D5]/35 to-[#028DC4]/30 blur-2xl"
      />

      <div className="relative z-10 grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <LoginBrandPanel role={state.role} registration />

        <section className="flex items-center justify-center px-5 py-10 sm:px-10 lg:px-8 xl:px-12">
          <RegistrationForm controller={controller} joinReturnTo={joinReturnTo} />
        </section>
      </div>
    </main>
  );
}
