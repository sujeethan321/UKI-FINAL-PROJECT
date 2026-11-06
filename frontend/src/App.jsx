
import {
  BrowserRouter,
  Route,
  Routes,
  Navigate,
} from "react-router-dom";


import LandingPage from "./pages/landing/LandingPage";

import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import { AuthProvider } from "./context/AuthContext.jsx";
import ProtectedRoute from "./routes/ProtectedRoute";
import DriverDeliveries from "./pages/driver/DriverDeliveries";
import AvailableJobs from "./pages/driver/AvailableJobs";
import DriverDashboard from "./pages/driver/DriverDashboard";
import DriverNotifications from "./pages/driver/DriverNotifications";
import DriverLayout from "./layouts/DriverLayout";
import TransactionHistory from "./pages/customer/TransactionHistory";
import CreditStatement from "./pages/customer/CreditStatement";
import MyShops from "./pages/customer/MyShops";
import CreditAccountDetails from "./pages/customer/CreditAccountDetails";
import CustomerLayout from "./layouts/CustomerLayout";
import CustomerDashboard from "./pages/customer/CustomerDashboard";
import CustomerNotifications from "./pages/customer/CustomerNotifications";
import ShopOwnerLayout from "./layouts/ShopOwnerLayout";
import ShopOwnerDashboard from "./pages/shopOwner/ShopOwnerDashboard";
import AdminLayout from "./layouts/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminBusinesses from "./pages/admin/AdminBusinesses";
import BusinessOnboarding from "./pages/shopOwner/BusinessOnboarding";
import ShopOwnerCustomers from "./pages/shopOwner/ShopOwnerCustomers";
import ShopOwnerCreditSales from "./pages/shopOwner/ShopOwnerCreditSales";

import ShopOwnerRepayments from "./pages/shopOwner/ShopOwnerRepayments";
import ShopOwnerDeliveries from "./pages/shopOwner/ShopOwnerDeliveries";

import NotificationProvider from "./context/NotificationProvider";
import AdminNotifications from "./pages/admin/AdminNotifications";

import ShopOwnerNotifications from "./pages/shopOwner/ShopOwnerNotifications";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
        <Routes>
          <Route
            path="/"
            element={<LandingPage />}
          />

          <Route
            path="/select-role"
            element={<Navigate to="/login" replace />}
          />

          <Route
            path="/login"
            element={<LoginPage />}
          />

          <Route path="/login/:role" element={<Navigate to="/login" replace />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/register/:role"
            element={<RegisterPage />}
          />


          {/* Customer-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["customer"]} />}>
            <Route path="/customer" element={<CustomerLayout />}>
              <Route path="dashboard" element={<CustomerDashboard />} />
              <Route path="shops" element={<MyShops />} />
              <Route path="transactions" element={<TransactionHistory />} />
              <Route path="credit/:accountId/statement" element={<CreditStatement />} />
              <Route path="credit/:accountId" element={<CreditAccountDetails />} />
              <Route path="notifications" element={<CustomerNotifications />} />
            </Route>
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
              <Route path="deliveries" element={<ShopOwnerDeliveries />} />
              <Route path="notifications" element={<ShopOwnerNotifications />} />
            </Route>
          </Route>


          {/* Delivery Driver-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["driver"]} />}>
            <Route element={<DriverLayout />}>
              <Route path="/driver/dashboard" element={<DriverDashboard />} />
              <Route path="/driver/deliveries" element={<DriverDeliveries />} />
              <Route path="/driver/deliveries/:deliveryId" element={<DriverDeliveries detail />} />
              <Route path="/driver/history" element={<DriverDeliveries history />} />
              <Route path="/driver/jobs" element={<AvailableJobs />} />
              <Route path="/driver/notifications" element={<DriverNotifications />} />
            </Route>
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
