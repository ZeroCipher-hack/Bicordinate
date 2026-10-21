import { useState } from 'react'
import { supabase } from '../supabase'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
    }

    setLoading(false)
  }

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error } = await supabase.auth.signUp({ email, password })
    if (error) {
      setError(error.message)
    } else {
      setError('Ro\'yxatdan o\'tdingiz! Email tasdiqlang.')
    }

    setLoading(false)
  }

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: '100%', maxWidth: '400px', padding: '1rem' }}>
        <div className="card">
          <h1 style={{ marginBottom: '1.5rem', color: '#7C4DFF' }}>Bicoordinate</h1>
          <form onSubmit={handleLogin}>
            {error && <div className="alert alert-error">{error}</div>}

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                style={{ width: '100%' }}
                disabled={loading}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Parol</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{ width: '100%' }}
                disabled={loading}
              />
            </div>

            <button style={{ width: '100%', marginBottom: '0.5rem' }} disabled={loading}>
              {loading ? 'Tekshirilmoqda...' : 'Kirish'}
            </button>
            <button
              type="button"
              onClick={handleSignup}
              style={{ width: '100%', background: '#FFC93C', color: '#000' }}
              disabled={loading}
            >
              Ro'yxatdan o'tish
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
