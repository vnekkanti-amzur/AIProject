import { Navigate, Route, Routes } from 'react-router-dom';
import { GoogleAuthCallback } from './components/auth/GoogleAuthCallback';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<GoogleAuthCallback />} />
      <Route path="/chat" element={<ChatPage />} />
    </Routes>
  );
}
