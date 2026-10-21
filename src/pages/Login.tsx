import { useState } from 'react'
import { supabase } from '../supabase'

declare global {
  interface Window {
    Telegram?: {
      Login?: {
        embedded?: unknown
        auth?: (options: { bot_id: string; request_access?: string }, callback: (user: Record<string, unknown>) => void) => void
      }
    }
  }
}

export default function Login() {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGoogle = async () => {
    setError('')
    setLoading(true)
    const { data, error: authErr } = await supabase.auth.signInWithOAuth({
      provider: 'google',
    })
    if (authErr) {
      setError(authErr.message)
    }
    setLoading(false)
  }

  const handleTelegram = async () => {
    setError('')
    setLoading(true)

    // Telegram Web App callback (frontend → bot → webhook)
    // Bot uchun: t.me/bicoordinate_bot (o'ndan o'tish)
    // Hozir: demo uchun mock callback
    if (window.Telegram?.Login?.auth) {
      window.Telegram.Login.auth({ bot_id: '7035378990', request_access: 'write' }, async (user: Record<string, unknown>) => {
        try {
          const res = await fetch('/functions/v1/telegram-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(user),
          })
          const data = await res.json()
          if (data.access_token) {
            await supabase.auth.setSession({
              access_token: data.access_token,
              refresh_token: data.refresh_token || '',
            })
          }
        } catch (err) {
          setError(String(err))
          setLoading(false)
        }
      })
    } else {
      setError('Telegram Login qurilmasi mavjud emas. Brauzer talab.')
      setLoading(false)
    }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: '100%', maxWidth: '400px', padding: '1rem' }}>
        <div className="card">
          <h1 style={{ marginBottom: '0.5rem', color: '#7C4DFF', textAlign: 'center' }}>Bicoordinate</h1>
          <p style={{ textAlign: 'center', color: '#666', marginBottom: '2rem', fontSize: '0.9rem' }}>
            Matematika va ingliz tilida AI ustoz
          </p>

          {error && <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>{error}</div>}

          <div style={{ display: 'grid', gap: '1rem', marginBottom: '1.5rem' }}>
            <button
              onClick={handleGoogle}
              disabled={loading}
              style={{
                background: '#fff',
                color: '#333',
                border: '1px solid #ddd',
                padding: '0.75rem',
                fontWeight: 600,
              }}
            >
              {loading ? 'Tekshirilmoqda...' : 'Google bilan kirish'}
            </button>

            <button
              onClick={handleTelegram}
              disabled={loading}
              style={{
                background: '#0088cc',
                color: '#fff',
                padding: '0.75rem',
                fontWeight: 600,
              }}
            >
              {loading ? 'Tekshirilmoqda...' : 'Telegram bilan kirish'}
            </button>
          </div>

          <p style={{ textAlign: 'center', fontSize: '0.85rem', color: '#999' }}>
            Davom etish orqali, siz <a href="#">Shartlarni</a> qabul qilasiz
          </p>
        </div>
      </div>

      {/* Telegram Web App script */}
      <script src="https://telegram.org/js/telegram-web-app.js"></script>
    </div>
  )
}
