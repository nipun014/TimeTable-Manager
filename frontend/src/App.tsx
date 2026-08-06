import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, RequireAuth, useAuth } from './lib/auth'
import Auth from './pages/Auth'
import Builder from './pages/Builder'
import DatasetList from './pages/DatasetList'
import Result from './pages/Result'

function TopBar() {
  const { user, signOut } = useAuth()
  if (!user) return null
  return (
    <header className="topbar">
      <Link className="brand" to="/">
        <span className="logo">🗓️</span> EduSchedule
      </Link>
      <div className="spacer" />
      <span className="dim">{user.email}</span>
      <button className="ghost sm" onClick={signOut}>
        Sign out
      </button>
    </header>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app">
          <TopBar />
          <Routes>
            <Route path="/login" element={<Auth />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <DatasetList />
                </RequireAuth>
              }
            />
            <Route
              path="/d/:id"
              element={
                <RequireAuth>
                  <Builder />
                </RequireAuth>
              }
            />
            <Route
              path="/d/:id/result"
              element={
                <RequireAuth>
                  <Result />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </AuthProvider>
    </BrowserRouter>
  )
}
