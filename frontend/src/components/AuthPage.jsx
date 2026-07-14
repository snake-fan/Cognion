import { useEffect, useState } from 'react'
import cognionLogo from '../assets/cognion_logo_dark.png'
import {
  forgotPassword,
  loginUser,
  registerUser,
  resendVerification,
  resetPassword,
  verifyEmail
} from '../services/api'

const query = new URLSearchParams(window.location.search)
const initialAction = query.get('action')
const initialToken = query.get('token') || ''

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState(initialAction === 'reset-password' ? 'reset' : initialAction === 'verify-email' ? 'verify' : 'login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (mode !== 'verify' || !initialToken) return
    window.history.replaceState({}, '', window.location.pathname)
    setLoading(true)
    verifyEmail(initialToken)
      .then((result) => setMessage(result.message))
      .catch((nextError) => setError(nextError.message))
      .finally(() => setLoading(false))
  }, [mode])

  useEffect(() => {
    if (mode === 'reset' && initialToken) {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [mode])

  function changeMode(nextMode) {
    setMode(nextMode)
    setMessage('')
    setError('')
    setPassword('')
  }

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')
    try {
      if (mode === 'login') {
        onAuthenticated(await loginUser(email, password))
      } else if (mode === 'register') {
        const result = await registerUser(email, password)
        setMessage(result.message)
        setMode('waiting')
      } else if (mode === 'forgot') {
        setMessage((await forgotPassword(email)).message)
      } else if (mode === 'reset') {
        setMessage((await resetPassword(initialToken, password)).message)
      } else if (mode === 'waiting') {
        setMessage((await resendVerification(email)).message)
      }
    } catch (nextError) {
      setError(nextError.message)
    } finally {
      setLoading(false)
    }
  }

  const titles = {
    login: '登录 Cognion',
    register: '创建账户',
    waiting: '验证你的邮箱',
    forgot: '找回密码',
    reset: '设置新密码',
    verify: '邮箱验证'
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <img className="auth-logo" src={cognionLogo} alt="Cognion" />
        <h1>{titles[mode]}</h1>
        {mode === 'verify' ? (
          <div className="auth-message">{loading ? '正在验证…' : message || error}</div>
        ) : (
          <form onSubmit={submit}>
            {mode !== 'reset' && (
              <label>
                邮箱
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </label>
            )}
            {['login', 'register', 'reset'].includes(mode) && (
              <label>
                密码
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  maxLength={128}
                  pattern="[!-~]{8,128}"
                  title="8–128 位英文字母、数字或半角特殊字符，不允许空格"
                  required
                />
              </label>
            )}
            {mode === 'waiting' && <p>验证邮件已发送。完成验证后再返回登录。</p>}
            {message && <p className="auth-success">{message}</p>}
            {error && <p className="auth-error">{error}</p>}
            <button className="auth-primary" type="submit" disabled={loading}>
              {loading ? '请稍候…' : mode === 'login' ? '登录' : mode === 'register' ? '注册' : mode === 'waiting' ? '重新发送' : mode === 'forgot' ? '发送重置邮件' : '重置密码'}
            </button>
          </form>
        )}
        <nav className="auth-links">
          {mode !== 'login' && <button onClick={() => changeMode('login')}>返回登录</button>}
          {mode === 'login' && <button onClick={() => changeMode('register')}>注册账户</button>}
          {mode === 'login' && <button onClick={() => changeMode('waiting')}>重发验证邮件</button>}
          {mode === 'login' && <button onClick={() => changeMode('forgot')}>忘记密码</button>}
        </nav>
      </section>
    </main>
  )
}
