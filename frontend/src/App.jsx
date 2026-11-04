
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  Link,
} from "react-router-dom";


import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import { AuthProvider } from "./context/AuthContext.jsx";
import ProtectedRoute from "./routes/ProtectedRoute";
import DashboardPlaceholder from "./pages/dashboard/DashboardPlaceholder";
import ShopOwnerLayout from "./layouts/ShopOwnerLayout";
import ShopOwnerDashboard from "./pages/shopOwner/ShopOwnerDashboard";
import AdminLayout from "./layouts/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminBusinesses from "./pages/admin/AdminBusinesses";
import BusinessOnboarding from "./pages/shopOwner/BusinessOnboarding";
import ShopOwnerCustomers from "./pages/shopOwner/ShopOwnerCustomers";
import ShopOwnerCreditSales from "./pages/shopOwner/ShopOwnerCreditSales";

import ShopOwnerRepayments from "./pages/shopOwner/ShopOwnerRepayments";

import NotificationProvider from "./context/NotificationProvider";
import AdminNotifications from "./pages/admin/AdminNotifications";

import ShopOwnerNotifications from "./pages/shopOwner/ShopOwnerNotifications";

const roleOptions = [
  { label: "Shop Owner", slug: "shop-owner" },
  { label: "Customer", slug: "customer" },
  { label: "Delivery Driver", slug: "driver" },
  { label: "Administrator", slug: "admin" },
];

function TemporaryRoleSelector() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[#F5F8FC] p-6">
      <h1 className="text-3xl font-bold text-[#10243E]">
        Welcome to LankaPex
      </h1>

      <p className="text-[#526887]">
        Select your role to log in.
      </p>

      <div className="grid w-full max-w-xl gap-4 sm:grid-cols-2">
        {roleOptions.map((role) => (
          <Link
            key={role.slug}
            to={`/login/${role.slug}`}
            className="rounded-xl border border-[#D8E5F0] bg-white p-6 text-center font-semibold text-[#10243E] shadow-sm hover:border-[#12B8A6]"
          >
            {role.label}
          </Link>
        ))}
      </div>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
        <Routes>
          <Route
            path="/"
            element={<Navigate to="/select-role" replace />}
          />

          <Route
            path="/select-role"
            element={<TemporaryRoleSelector />}
          />

          <Route
            path="/login/:role"
            element={<LoginPage />}
          />

          <Route
            path="/register/:role"
            element={<RegisterPage />}
          />


          {/* Customer-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["customer"]} />}>
            <Route
              path="/customer/dashboard"
              element={<DashboardPlaceholder />}
            />
          </Route>

          {/* Shop Owner-only pages */}


          {/* Shop Owner protected pages */}
          <Route element={<ProtectedRoute allowedRoles={["shop_owner"]} />}>
            <Route path="/shop-owner" element={<ShopOwnerLayout />}>
              <Route
                path="dashboard"
                element={<ShopOwnerDashboard />}
              />

              <Route
                path="business/register"
                element={<BusinessOnboarding />}
              />

              <Route
                path="customers"
                element={<ShopOwnerCustomers />}
              />
              <Route path="credit-sales" element={<ShopOwnerCreditSales />} />
              <Route path="repayments" element={<ShopOwnerRepayments />} />
              <Route path="notifications" element={<ShopOwnerNotifications />} />
            </Route>
          </Route>


          {/* Delivery Driver-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["driver"]} />}>
            <Route
              path="/driver/dashboard"
              element={<DashboardPlaceholder />}
            />
          </Route>

          {/* Administrator-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="notifications" element={<AdminNotifications />} />
              <Route
                path="dashboard"
                element={<AdminDashboard />}
              />
              <Route
                path="businesses"
                element={<AdminBusinesses />}
              />
            </Route>
          </Route>

        </Routes>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}