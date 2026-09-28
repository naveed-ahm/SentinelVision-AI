import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Monitoring from "./pages/Monitoring";
import Cameras from "./pages/Cameras";
import Analytics from "./pages/Analytics";
import VehicleSearch from "./pages/VehicleSearch";
import Watchlist from "./pages/Watchlist";
import Tracking from "./pages/Tracking";
import GisMap from "./pages/GisMap";
import Alerts from "./pages/Alerts";
import Events from "./pages/Events";
import Reports from "./pages/Reports";
import Health from "./pages/Health";
import Users from "./pages/Users";
import Settings from "./pages/Settings";
import { useAuth } from "./context/AuthContext";
import { LiveProvider } from "./context/LiveContext";
import { Spinner } from "./components/ui";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner className="h-8 w-8 text-accent-bright" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <LiveProvider>{children}</LiveProvider>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/" element={<Overview />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/vehicles" element={<VehicleSearch />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/tracking" element={<Tracking />} />
        <Route path="/map" element={<GisMap />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/events" element={<Events />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/health" element={<Health />} />
        <Route path="/users" element={<Users />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
