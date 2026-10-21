import { useEffect, useState } from 'react'
import { supabase } from '../supabase'

interface Profile {
  id: string
  full_name: string
  role: string
  xp: number
  streak: number
}

interface Course {
  id: string
  title: string
  teacher_id: string
  price_uzs: number
  status: string
}

interface Teacher {
  id: string
  display_name: string
  subject: string
  bio: string
}

export default function Dashboard() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [teachers, setTeachers] = useState<Map<string, Teacher>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      // Profile yuklash
      const { data: profileData, error: profileErr } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single()
      if (profileErr) throw profileErr
      setProfile(profileData)

      // Faol kurslarni yuklash
      const { data: coursesData, error: coursesErr } = await supabase
        .from('courses')
        .select('*')
        .eq('status', 'active')
        .limit(10)
      if (coursesErr) throw coursesErr
      setCourses(coursesData || [])

      // Ustozlarni yuklash
      if (coursesData && coursesData.length > 0) {
        const teacherIds = [...new Set(coursesData.map(c => c.teacher_id))]
        const { data: teachersData, error: teachersErr } = await supabase
          .from('teachers')
          .select('*')
          .in('id', teacherIds)
        if (teachersErr) throw teachersErr
        const teacherMap = new Map(teachersData?.map(t => [t.id, t]) || [])
        setTeachers(teacherMap)
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  if (loading) return <div className="container" style={{ paddingTop: '2rem' }}>Yuklanmoqda...</div>

  return (
    <>
      <header className="header">
        <div className="header-content">
          <div className="logo">Bicoordinate</div>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span>{profile?.full_name || 'Foydalanuvchi'}</span>
            <button onClick={handleLogout} style={{ background: '#ccc', color: '#333' }}>
              Chiqish
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        {error && <div className="alert alert-error">{error}</div>}

        {/* Stats */}
        <div className="stats">
          <div className="stat-box">
            <div className="stat-value">{profile?.xp || 0}</div>
            <div className="stat-label">XP Nuqtalar</div>
          </div>
          <div className="stat-box">
            <div className="stat-value">{profile?.streak || 0}</div>
            <div className="stat-label">Kunlar Zanjiri</div>
          </div>
          <div className="stat-box">
            <div className="stat-value">{courses.length}</div>
            <div className="stat-label">Mavjud Kurslar</div>
          </div>
        </div>

        {/* Kunlik Mashqlar */}
        <section style={{ marginBottom: '3rem' }}>
          <h2 style={{ marginBottom: '1.5rem', color: '#7C4DFF' }}>Kunlik Mashqlar</h2>
          <div className="card">
            <p>Bugunning mashqlarini boshlash uchun <a href="#daily">quyiga</a> o'tish qilib kiriting.</p>
          </div>
        </section>

        {/* Kurslar */}
        <section>
          <h2 style={{ marginBottom: '1.5rem', color: '#7C4DFF' }}>Faol Kurslar</h2>
          {courses.length === 0 ? (
            <div className="card">
              <p>Hozircha kurslar yo'q. Ustozlarni tanlang va kurs sotib oling.</p>
            </div>
          ) : (
            <div className="grid">
              {courses.map((course) => {
                const teacher = teachers.get(course.teacher_id)
                return (
                  <div key={course.id} className="course-card">
                    <div className="course-card-header">
                      <div className="course-card-title">{course.title}</div>
                      <div className="course-card-teacher">
                        {teacher?.display_name || 'Noma\'lum Ustoz'}
                      </div>
                    </div>
                    <div className="course-card-body">
                      <div className="course-card-price">{(course.price_uzs / 100).toLocaleString()} so'm</div>
                      <div style={{ marginBottom: '1rem' }}>
                        <span className="badge">{teacher?.subject || ''}</span>
                      </div>
                      <button className="course-card-btn">Kursga O'tish</button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </main>
    </>
  )
}
