import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { ProviderRoute } from './auth/ProviderRoute';
import { AppLayout } from './components/AppLayout';
import { ProviderLayout } from './components/ProviderLayout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ProviderLoginPage } from './pages/ProviderLoginPage';
import { ProviderRegisterPage } from './pages/ProviderRegisterPage';
import { ProviderDashboardPage } from './pages/ProviderDashboardPage';
import { ProviderPatientDetailPage } from './pages/ProviderPatientDetailPage';
import { HomePage } from './pages/HomePage';
import { CyclePage } from './pages/CyclePage';
import { AssistantPage } from './pages/AssistantPage';
import { InsightsPage } from './pages/InsightsPage';
import { ProfilePage } from './pages/ProfilePage';
import { SettingsPage } from './pages/SettingsPage';
import { DataPrivacyPage } from './pages/DataPrivacyPage';
import { SharingPage } from './pages/SharingPage';
import { SmsPage } from './pages/SmsPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { RouteErrorBoundary } from './components/ErrorBoundary';
import { CustomCursor } from './components/CustomCursor';
import { ScrollToTopButton } from './components/ScrollToTopButton';
import { DocumentLanguage } from './lib/useDocumentMeta';
import { SkipToContent } from './components/SkipToContent';
import { RouteAnnouncer } from './components/RouteAnnouncer';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* Keeps <html lang> and <html dir> pointed at the active locale
            (#407). Rendered once here rather than per page: it is a
            property of the app, not of a route, and a screen reader picks
            its speech synthesizer from that attribute — pinned to "en" it
            read Devanagari and Tamil in an English voice. */}
        <DocumentLanguage />

        {/* First in the tree so it is the first thing Tab reaches from the
            address bar — a skip link that is not first skips nothing
            (#409). */}
        <SkipToContent />

        {/* Announces the new page and moves focus into <main> on every
            navigation. A client-side route change fires no load event, so
            without this the DOM swaps and assistive technology is told
            nothing at all. */}
        <RouteAnnouncer />

        <CustomCursor />
        <ScrollToTopButton />

        {/* Inside the router so it can clear itself when the route changes,
            and around <Routes> so it catches a throw from any page rather
            than needing one boundary per route. */}
        <RouteErrorBoundary>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/provider/login" element={<ProviderLoginPage />} />
            <Route path="/provider/register" element={<ProviderRegisterPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<HomePage />} />
              <Route path="/cycle" element={<CyclePage />} />
              <Route path="/assistant" element={<AssistantPage />} />
              <Route path="/insights" element={<InsightsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/data" element={<DataPrivacyPage />} />
              <Route path="/sharing" element={<SharingPage />} />
              <Route path="/sms" element={<SmsPage />} />
            </Route>
            <Route
              element={
                <ProviderRoute>
                  <ProviderLayout />
                </ProviderRoute>
              }
            >
              <Route path="/provider" element={<ProviderDashboardPage />} />
              <Route
                path="/provider/patients/:patientId"
                element={<ProviderPatientDetailPage />}
              />
            </Route>
            {/* A real 404 instead of a silent redirect to "/" — see
                pages/NotFoundPage.tsx for why that redirect was worse than
                it looked. */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </RouteErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  );
}
