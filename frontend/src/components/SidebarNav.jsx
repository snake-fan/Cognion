function SidebarNav({
  collapsed,
  onToggleCollapsed,
  logoSrc,
  items,
  icons,
  activeKey,
  onItemClick
}) {
  return (
    <aside className={`left-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button className="logo-button" onClick={() => onToggleCollapsed((value) => !value)}>
          <img className="logo-image" src={logoSrc} alt="Cognion" />
        </button>
      </div>
      <div className="sidebar-content">
        {items.map((item) => (
          <button
            key={item.key}
            className={`feature-item ${activeKey === item.key ? 'active' : ''} ${item.enabled ? '' : 'disabled'}`}
            onClick={() => onItemClick(item.key, item.enabled)}
            title={item.label}
            aria-label={item.label}
          >
            <span className="feature-item-icon">{icons[item.key]}</span>
            {!collapsed ? <span className="feature-item-label">{item.label}</span> : null}
          </button>
        ))}
      </div>
    </aside>
  )
}

export default SidebarNav
