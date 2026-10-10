import { createBrowserRouter } from 'react-router'
import { RequireWarden } from './auth/RequireWarden'
import { Layout } from './components/Layout'
import { Absentees } from './pages/Absentees'
import { Enrollment } from './pages/Enrollment'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'
import { Review } from './pages/Review'
import { Room } from './pages/Room'
import { Tonight } from './pages/Tonight'
import { Windows } from './pages/Windows'

export const router = createBrowserRouter([
  { path: '/', element: <Landing /> },
  { path: '/login', element: <Login /> },
  {
    element: <RequireWarden />,
    children: [
      {
        path: '/dashboard',
        element: <Layout />,
        children: [
          { index: true, element: <Tonight /> },
          { path: 'review', element: <Review /> },
          { path: 'absentees', element: <Absentees /> },
          { path: 'rooms/:roomId', element: <Room /> },
          { path: 'windows', element: <Windows /> },
          { path: 'enrollment', element: <Enrollment /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFound /> },
])
