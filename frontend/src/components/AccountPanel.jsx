import { useState } from 'react'
import { changeUserPassword, deleteUserAccount, updateUserMetadata } from '../services/api'

export default function AccountPanel({ user, onClose, onUserChange, onSignedOut }) {
  const [metadata, setMetadata] = useState(user.metadata)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function saveMetadata(event) {
    event.preventDefault()
    try {
      const result = await updateUserMetadata(metadata)
      onUserChange({ ...user, metadata: result.metadata })
      setMessage('资料已保存')
      setError('')
    } catch (nextError) {
      setError(nextError.message)
    }
  }

  async function changePassword(event) {
    event.preventDefault()
    try {
      await changeUserPassword(currentPassword, newPassword)
      onSignedOut()
    } catch (nextError) {
      setError(nextError.message)
    }
  }

  async function deleteAccount() {
    if (!window.confirm('此操作会永久删除账户、论文、笔记和知识图谱，且无法恢复。确定继续吗？')) return
    try {
      await deleteUserAccount(deletePassword)
      onSignedOut()
    } catch (nextError) {
      setError(nextError.message)
    }
  }

  return (
    <div className="account-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="account-panel" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <header><h2>账户设置</h2><button onClick={onClose}>关闭</button></header>
        <p className="account-email">{user.email} · 已验证</p>
        <button type="button" onClick={onSignedOut}>退出当前设备</button>
        <form onSubmit={saveMetadata}>
          <label>显示名称<input value={metadata.display_name} onChange={(event) => setMetadata({ ...metadata, display_name: event.target.value })} /></label>
          <label>头像 URL<input value={metadata.avatar_url || ''} onChange={(event) => setMetadata({ ...metadata, avatar_url: event.target.value })} /></label>
          <label>语言<input value={metadata.locale} onChange={(event) => setMetadata({ ...metadata, locale: event.target.value })} /></label>
          <label>时区<input value={metadata.timezone} onChange={(event) => setMetadata({ ...metadata, timezone: event.target.value })} /></label>
          <button type="submit">保存资料</button>
        </form>
        <form onSubmit={changePassword}>
          <h3>修改密码</h3>
          <label>当前密码<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
          <label>新密码<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} pattern="[!-~]{8,128}" required /></label>
          <button type="submit">修改并退出所有设备</button>
        </form>
        <div className="account-danger">
          <h3>永久删除账户</h3>
          <input type="password" placeholder="输入密码确认" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} />
          <button onClick={deleteAccount} disabled={!deletePassword}>永久删除</button>
        </div>
        {message && <p className="auth-success">{message}</p>}
        {error && <p className="auth-error">{error}</p>}
      </section>
    </div>
  )
}
