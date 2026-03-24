function WorkspaceLayout({
  isResizing,
  leftSidebar,
  centerContent,
  rightSidebar,
  rightCollapsed,
  onResizeHandleMouseDown,
  rightStyle,
  rightSidebarRef,
  showRightSidebar = true
}) {
  return (
    <div className={`app-shell ${isResizing ? 'is-resizing' : ''}`}>
      {leftSidebar}
      {centerContent}
      {showRightSidebar ? (
        <>
          {!rightCollapsed ? <div className="resize-handle" onMouseDown={onResizeHandleMouseDown} /> : null}
          <aside ref={rightSidebarRef} className="right-sidebar" style={rightStyle}>
            {rightSidebar}
          </aside>
        </>
      ) : null}
    </div>
  )
}

export default WorkspaceLayout
