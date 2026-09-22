import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Orders from "./pages/Orders";
import OrderForm from "./pages/OrderForm";
import OrderDetail from "./pages/OrderDetail";
import Customers from "./pages/Customers";
import Products from "./pages/Products";
import Colors from "./pages/Colors";
import Users from "./pages/Users";
import Revenue from "./pages/Revenue";
import Production from "./pages/Production";
import ProductionPrint from "./pages/ProductionPrint";
import ClientPrint from "./pages/ClientPrint";
import Profile from "./pages/Profile";

function Protected({ children, admin }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* Print previews render standalone (no sidebar) so the preview matches what actually prints */}
          <Route path="/orders/:id/production-print" element={<Protected admin><ProductionPrint /></Protected>} />
          <Route path="/orders/:id/client-print" element={<Protected><ClientPrint /></Protected>} />
          <Route path="/" element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="orders/new" element={<OrderForm />} />
            <Route path="orders" element={<Orders />} />
            <Route path="orders/:id" element={<OrderDetail />} />
            <Route path="orders/:id/edit" element={<Protected admin><OrderForm /></Protected>} />
            <Route path="production" element={<Protected admin><Production /></Protected>} />
            <Route path="revenue" element={<Protected admin><Revenue /></Protected>} />
            <Route path="customers" element={<Customers />} />
            <Route path="products" element={<Protected admin><Products /></Protected>} />
            <Route path="colors" element={<Protected admin><Colors /></Protected>} />
            <Route path="users" element={<Protected admin><Users /></Protected>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </AuthProvider>
  );
}
