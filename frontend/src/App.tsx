import { Routes, Route } from 'react-router-dom'
import { IncidentList } from './components/IncidentList'
import { InvestigationDetail } from './components/InvestigationDetail'
import { IncidentCreate } from './pages/IncidentCreate'
import { Header } from './components/Header'

function App() {
  return (
    <div className="min-h-screen bg-dark-50 dark:bg-dark-950">
      <Header />
      <main className="container mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<IncidentList />} />
          <Route path="/create" element={<IncidentCreate />} />
          <Route path="/investigation/:investigationId" element={<InvestigationDetail />} />
        </Routes>
      </main>
    </div>
  )
}

export default App