import { Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Report from "./pages/Report";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/rapport/:id" element={<Report />} />
    </Routes>
  );
}
