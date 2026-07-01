import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { GameRoute } from './pages/GameRoute'
import { HomePage } from './pages/HomePage'
import { JoinPage } from './pages/JoinPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/join/:gameId" element={<JoinPage />} />
        <Route path="/games/:gameId" element={<GameRoute />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
