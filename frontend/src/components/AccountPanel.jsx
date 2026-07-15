import { useState } from 'react'
import { changeUserPassword, deleteUserAccount, updateUserMetadata } from '../services/api'

function Icon({ name }) {
  const paths = {
    close: <><path d="M6 6l12 12M18 6 6 18" /></>,
    user: <><circle cx="12" cy="8" r="3.5" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" /></>,
    logout: <><path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" /></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>
  }
  return <svg className="account-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export default function AccountPanel({ user, onClose, onUserChange, onSignedOut }) {
  const [metadata, setMetadata] = useState(user.metadata || {})
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const displayName = metadata.display_name || user.email.split('@')[0]
  const avatarInitial = displayName.slice(0, 1).toUpperCase()

  async function saveMetadata(event) {
    event.preventDefault()
    try {
      const result = await updateUserMetadata(metadata)
      onUserChange({ ...user, metadata: result.metadata })
      setMessage('个人资料已保存')
      setError('')
    } catch (nextError) {
      setError(nextError.message)
      setMessage('')
    }
  }

  async function changePassword(event) {
    event.preventDefault()
    try {
      await changeUserPassword(currentPassword, newPassword)
      onSignedOut()
    } catch (nextError) {
      setError(nextError.message)
      setMessage('')
    }
  }

  async function deleteAccount() {
    if (!window.confirm('此操作会永久删除账户、论文、笔记和知识图谱，且无法恢复。确定继续吗？')) return
    try {
      await deleteUserAccount(deletePassword)
      onSignedOut()
    } catch (nextError) {
      setError(nextError.message)
      setMessage('')
    }
  }

  return (
    <div className="account-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="account-panel" role="dialog" aria-modal="true" aria-labelledby="account-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="account-panel-header">
          <div><span className="account-overline">SETTINGS</span><h2 id="account-title">账户设置</h2></div>
          <button className="account-icon-button" type="button" onClick={onClose} aria-label="关闭账户设置"><Icon name="close" /></button>
        </header>

        <div className="account-profile-summary">
          <div className="account-avatar">
            {metadata.avatar_url ? <img src={metadata.avatar_url} alt="" /> : avatarInitial}
          </div>
          <div className="account-identity">
            <strong>{displayName}</strong>
            <span>{user.email}</span>
            <small><Icon name="check" /> 邮箱已验证</small>
          </div>
          <button className="account-logout-button" type="button" onClick={onSignedOut}><Icon name="logout" />退出</button>
        </div>

        {(message || error) && <div className={`account-notice ${error ? 'is-error' : 'is-success'}`}>{error || message}</div>}

        <form className="account-section" onSubmit={saveMetadata}>
          <div className="account-section-heading">
            <span className="account-section-icon"><Icon name="user" /></span>
            <div><h3>个人资料</h3><p>管理你在 Cognion 中展示的信息</p></div>
          </div>
          <div className="account-field-grid">
            <label>显示名称<input value={metadata.display_name || ''} onChange={(event) => setMetadata({ ...metadata, display_name: event.target.value })} placeholder="你的名称" /></label>
            <label>头像 URL<input value={metadata.avatar_url || ''} onChange={(event) => setMetadata({ ...metadata, avatar_url: event.target.value })} placeholder="https://…" /></label>
            <label><span><Icon name="globe" />语言</span><input value={metadata.locale || ''} onChange={(event) => setMetadata({ ...metadata, locale: event.target.value })} placeholder="zh-CN" /></label>
            <label>时区<input value={metadata.timezone || ''} onChange={(event) => setMetadata({ ...metadata, timezone: event.target.value })} placeholder="Asia/Shanghai" /></label>
          </div>
          <div className="account-section-actions"><button className="account-primary-button" type="submit">保存更改</button></div>
        </form>

        <form className="account-section" onSubmit={changePassword}>
          <div className="account-section-heading">
            <span className="account-section-icon"><Icon name="lock" /></span>
            <div><h3>登录与安全</h3><p>更新密码后将退出所有已登录设备</p></div>
          </div>
          <div className="account-field-grid">
            <label>当前密码<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required /></label>
            <label>新密码<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" pattern="[!-~]{8,128}" title="8–128 位英文字母、数字或半角特殊字符" required /></label>
          </div>
          <div className="account-section-actions"><button className="account-secondary-button" type="submit">更新密码</button></div>
        </form>

        <section className="account-section account-danger">
          <div className="account-section-heading">
            <span className="account-section-icon"><Icon name="trash" /></span>
            <div><h3>删除账户</h3><p>账户及所有论文、笔记和知识图谱将被永久删除</p></div>
          </div>
          <label>输入密码以确认<input type="password" placeholder="当前密码" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} /></label>
          <div className="account-section-actions"><button type="button" onClick={deleteAccount} disabled={!deletePassword}>永久删除账户</button></div>
        </section>
      </section>
    </div>
  )
}
