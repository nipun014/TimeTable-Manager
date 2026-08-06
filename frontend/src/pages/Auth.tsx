import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Auth() {
  const { user, loading, setUser } = useAuth()
  const location = useLocation() as { state?: { from?: string } }
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) return <div className="page dim">Loading…</div>
  if (user) return <Navigate to={location.state?.from ?? '/'} replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const fn = mode === 'login' ? api.login : api.signup
      const res = await fn(email, password)
      setUser(res.user)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="authwrap">
      <div className="authbox stack">
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '2rem' }}>🗓️</div>
          <h1>EduSchedule</h1>
          <p className="muted" style={{ marginTop: '.35rem' }}>
            Conflict-free timetables, solved with OR-Tools CP-SAT.
          </p>
        </div>

        <form className="card stack" onSubmit={submit}>
          <div>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@college.edu"
            />
          </div>
          <div>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={mode === 'signup' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? 'At least 8 characters' : ''}
            />
          </div>

          {error && <div className="banner error">{error}</div>}

          <button className="primary" type="submit" disabled={busy}>
            {busy ? <span className="spin" /> : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>

          <p className="dim" style={{ textAlign: 'center' }}>
            {mode === 'login' ? 'No account yet?' : 'Already have an account?'}{' '}
            <button
              type="button"
              className="ghost sm"
              onClick={() => {
                setMode(mode === 'login' ? 'signup' : 'login')
                setError('')
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </form>
      </div>
    </div>
  )
}
