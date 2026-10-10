import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Enrollment } from './pages/Enrollment'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'
import { Room } from './pages/Room'
import { Tonight } from './pages/Tonight'
import { Windows } from './pages/Windows'

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Tonight /> },
      { path: '/rooms/:roomId', element: <Room /> },
      { path: '/windows', element: <Windows /> },
      { path: '/enrollment', element: <Enrollment /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])
