import ShoppingCart from './pages/customer/ShoppingCart';
import OrderHistory from './pages/customer/OrderHistory';

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
import DriverEarnings from "./pages/driver/DriverEarnings";
import DriverVehicle from "./pages/driver/DriverVehicle";
import DriverProfile from "./pages/driver/DriverProfile";
import DriverSettings from "./pages/driver/DriverSettings";
import DriverNotifications from "./pages/driver/DriverNotifications";
import DriverLayout from "./layouts/DriverLayout";
import TransactionHistory from "./pages/customer/TransactionHistory";
import CreditStatement from "./pages/customer/CreditStatement";
import MyShops from "./pages/customer/MyShops";
import JoinShop from "./pages/customer/JoinShop";
import CreditAccountDetails from "./pages/customer/CreditAccountDetails";
import CustomerLayout from "./layouts/CustomerLayout";
import CustomerDashboard from "./pages/customer/CustomerDashboard";
import CustomerCreditAccounts from "./pages/customer/CustomerCreditAccounts";
import CustomerDeliveries from "./pages/customer/CustomerDeliveries";
import CustomerProfile from "./pages/customer/CustomerProfile";
import CustomerSettings from "./pages/customer/CustomerSettings";
import CustomerNotifications from "./pages/customer/CustomerNotifications";
import ShopOwnerLayout from "./layouts/ShopOwnerLayout";
import ShopOwnerDashboard from "./pages/shopOwner/ShopOwnerDashboard";
import AdminLayout from "./layouts/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminBusinesses from "./pages/admin/AdminBusinesses";
import AdminManagement from "./pages/admin/AdminManagement";
import BusinessOnboarding from "./pages/shopOwner/BusinessOnboarding";
import ShopOwnerCustomers from "./pages/shopOwner/ShopOwnerCustomers";
import ShopOwnerCreditSales from "./pages/shopOwner/ShopOwnerCreditSales";

import ShopOwnerRepayments from "./pages/shopOwner/ShopOwnerRepayments";
import ShopOwnerDeliveries from "./pages/shopOwner/ShopOwnerDeliveries";
import ShopOwnerProducts from "./pages/shopOwner/ShopOwnerProducts";
import ShopOwnerReports from "./pages/shopOwner/ShopOwnerReports";
import ShopOwnerSettings from "./pages/shopOwner/ShopOwnerSettings";
import SubscriptionBilling from "./pages/shopOwner/SubscriptionBilling";
import CustomerCatalogue from "./pages/customer/CustomerCatalogue";

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
          <Route path="/join/:publicCode" element={<JoinShop />} />

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
              <Route index element={<Navigate to="/customer/dashboard" replace />} />
              <Route path="dashboard" element={<CustomerDashboard />} />
              <Route path="credit-accounts" element={<CustomerCreditAccounts />} />
              <Route path="deliveries" element={<CustomerDeliveries />} />
              <Route path="profile" element={<CustomerProfile />} />
              <Route path="settings" element={<CustomerSettings />} />
              <Route path="shops" element={<MyShops />} />
<Route path="cart" element={<ShoppingCart />} />
<Route path="checkout" element={<ShoppingCart checkout />} />
<Route path="orders" element={<OrderHistory />} />
<Route path="orders/:orderId" element={<OrderHistory />} />
              <Route path="shops/explore" element={<CustomerCatalogue />} />
              <Route path="explore/:businessId" element={<CustomerCatalogue mode="shop" />} />
              <Route path="explore/:businessId/products/:productId" element={<CustomerCatalogue mode="product" />} />
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
              <Route index element={<Navigate to="/shop-owner/dashboard" replace />} />
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
              <Route path="products" element={<ShopOwnerProducts />} />
              <Route path="reports" element={<ShopOwnerReports />} />
              <Route path="settings" element={<ShopOwnerSettings />} />
              <Route path="subscription" element={<SubscriptionBilling />} />
<Route path="orders" element={<OrderHistory owner />} />
<Route path="orders/:orderId" element={<OrderHistory owner />} />
<Route path="credit-orders" element={<Navigate to="/shop-owner/orders" replace />} />
              <Route path="notifications" element={<ShopOwnerNotifications />} />
            </Route>
          </Route>


          {/* Delivery Driver-only pages */}
          <Route element={<ProtectedRoute allowedRoles={["driver"]} />}>
            <Route element={<DriverLayout />}>
              <Route path="/driver" element={<Navigate to="/driver/dashboard" replace />} />
              <Route path="/driver/dashboard" element={<DriverDashboard />} />
              <Route path="/driver/earnings" element={<DriverEarnings />} />
              <Route path="/driver/vehicle" element={<DriverVehicle />} />
              <Route path="/driver/profile" element={<DriverProfile />} />
              <Route path="/driver/settings" element={<DriverSettings />} />
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
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="shop-owners" element={<AdminManagement kind="shop_owner" />} />
              <Route path="customers" element={<AdminManagement kind="customer" />} />
              <Route path="drivers" element={<AdminManagement kind="driver" />} />
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

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
