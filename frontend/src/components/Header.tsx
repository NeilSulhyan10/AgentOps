import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Shield, Zap, Brain, Sun, Moon, Monitor } from 'lucide-react'
import { Button } from './ui/Button'

export function Header() {
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system')

  useEffect(() => {
    const stored = localStorage.getItem('theme') as 'light' | 'dark' | 'system' | null
    if (stored) {
      setTheme(stored)
    }
  }, [])

  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')
    
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }
    
    localStorage.setItem('theme', theme)
  }, [theme])

  const cycleTheme = () => {
    const themes: ('light' | 'dark' | 'system')[] = ['light', 'dark', 'system']
    const currentIndex = themes.indexOf(theme)
    const nextIndex = (currentIndex + 1) % themes.length
    setTheme(themes[nextIndex])
  }

  const themeIcons = {
    light: Sun,
    dark: Moon,
    system: Monitor
  }

  const themeLabels = {
    light: 'Light',
    dark: 'Dark',
    system: 'System'
  }

  const ThemeIcon = themeIcons[theme]

  return (
    <header className="border-b border-dark-200 dark:border-dark-800 bg-white/80 dark:bg-dark-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-dark-900 dark:text-dark-100">AgentOps</h1>
              <p className="text-xs text-dark-500 dark:text-dark-400">Adaptive Multi-Agent DevOps Investigation</p>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 text-sm text-dark-500 dark:text-dark-400">
              <Zap className="h-4 w-4" />
              <span>Adaptive Routing</span>
            </div>
            <div className="flex items-center gap-1 text-sm text-dark-500 dark:text-dark-400">
              <Brain className="h-4 w-4" />
              <span>Confidence Scoring</span>
            </div>
            <div className="flex items-center gap-1 text-sm text-dark-500 dark:text-dark-400">
              <Shield className="h-4 w-4" />
              <span>Deterministic</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={cycleTheme}
              className="relative"
              title={`Theme: ${themeLabels[theme]} (click to cycle)`}
            >
              <ThemeIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}