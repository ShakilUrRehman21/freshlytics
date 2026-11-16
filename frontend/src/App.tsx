import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import Guide from './pages/Guide';
import HistoryPage from './pages/History';
import Login from './pages/Login';
import Register from './pages/Register';
import ScanPage from './pages/ScanPage';
import Settings from './pages/Settings';

function App() {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />

                    <Route element={<ProtectedRoute />}>
                        <Route path="/" element={<Layout />}>
                            <Route index element={<Dashboard />} />
                            <Route path="scan" element={<ScanPage />} />
                            <Route path="history" element={<HistoryPage />} />
                            <Route path="guide" element={<Guide />} />
                            <Route path="settings" element={<Settings />} />
                            {/* old links */}
                            <Route path="analytics" element={<Navigate to="/history" replace />} />
                            <Route path="insights" element={<Navigate to="/guide" replace />} />
                        </Route>
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </Router>
        </AuthProvider>
    );
}

export default App;
