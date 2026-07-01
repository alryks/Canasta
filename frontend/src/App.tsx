import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { HomePage } from './pages/HomePage'
import { JoinPage } from './pages/JoinPage'
import { LobbyPage } from './pages/LobbyPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/join/:gameId" element={<JoinPage />} />
        <Route path="/games/:gameId" element={<LobbyPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
