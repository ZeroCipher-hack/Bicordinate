import { useEffect, useState } from 'react'
import { supabase } from './supabase'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'

function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => subscription?.unsubscribe()
  }, [])

  if (loading) return <div className="container" style={{ paddingTop: '2rem' }}>Yuklanmoqda...</div>

  return session ? <Dashboard /> : <Login />
}

export default App
