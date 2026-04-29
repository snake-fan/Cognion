import { useRef, useState } from 'react'

const CANVAS_WIDTH = 1040
const CANVAS_HEIGHT = 720
const MIN_VIEWBOX_WIDTH = 360
const MAX_VIEWBOX_WIDTH = 2200
const UNIT_TYPE_LAYOUT_ORDER = ['claim', 'method', 'question', 'concept']

function unitColor(unitType) {
  const normalizedType = String(unitType || '').toLowerCase()
  if (normalizedType === 'claim') {
    return '#FEBB2A'
  }
  if (normalizedType === 'method') {
    return '#5fd6c7'
  }
  if (normalizedType === 'question') {
    return '#ff7b72'
  }
  return '#7ab8ff'
}

function compareUnitType(left, right) {
  const leftType = String(left || 'concept').toLowerCase()
  const rightType = String(right || 'concept').toLowerCase()
  const leftIndex = UNIT_TYPE_LAYOUT_ORDER.indexOf(leftType)
  const rightIndex = UNIT_TYPE_LAYOUT_ORDER.indexOf(rightType)
  const leftRank = leftIndex === -1 ? UNIT_TYPE_LAYOUT_ORDER.length : leftIndex
  const rightRank = rightIndex === -1 ? UNIT_TYPE_LAYOUT_ORDER.length : rightIndex
  if (leftRank !== rightRank) {
    return leftRank - rightRank
  }
  return leftType.localeCompare(rightType)
}

function estimateEdgeLabelWidth(text, compact = false) {
  if (compact) {
    return 22
  }
  return Math.max(30, String(text || '').length * 7 + 18)
}

function formatNodeLabel(text) {
  const label = String(text || '').trim()
  if (label.length <= 22) {
    return label
  }
  return `${label.slice(0, 21)}...`
}

function buildEdgeLabelLayouts(from, to, relations, nodeRadius = 32) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const tangentX = dx / length
  const tangentY = dy / length
  const normalX = -dy / length
  const normalY = dx / length
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI
  const normalizedAngle = angle > 90 || angle < -90 ? angle + 180 : angle
  const labels = Array.isArray(relations) ? relations : []
  const gap = 12
  const compactWidth = estimateEdgeLabelWidth('...', true)
  const safeStart = nodeRadius + 18
  const safeEnd = Math.max(safeStart, length - 28)
  const availableSpan = Math.max(0, safeEnd - safeStart)
  const widths = labels.map((label) => estimateEdgeLabelWidth(label))
  const compactFlags = labels.map(() => false)

  function currentTotalWidth() {
    return widths.reduce((sum, width, index) => sum + width + (index === 0 ? 0 : gap), 0)
  }

  if (availableSpan <= 0) {
    compactFlags.fill(true)
    widths.fill(compactWidth)
  } else {
    while (currentTotalWidth() > availableSpan) {
      let longestIndex = -1
      for (let index = 0; index < widths.length; index += 1) {
        if (compactFlags[index]) {
          continue
        }
        if (longestIndex === -1 || widths[index] > widths[longestIndex]) {
          longestIndex = index
        }
      }
      if (longestIndex === -1) {
        break
      }
      compactFlags[longestIndex] = true
      widths[longestIndex] = compactWidth
    }
  }

  let cursor = safeStart
  return labels.map((relation, index) => {
    const width = widths[index]
    const tangentOffset = Math.min(cursor + width / 2, safeEnd)
    const rank = Math.floor(index / 2)
    const side = index % 2 === 0 ? -1 : 1
    cursor += width + gap
    return {
      x: from.x + tangentX * tangentOffset + normalX * (10 + rank * 12) * side,
      y: from.y + tangentY * tangentOffset + normalY * (10 + rank * 12) * side,
      text: compactFlags[index] ? '...' : relation,
      isCompact: compactFlags[index],
      angle: normalizedAngle
    }
  })
}

function backgroundRectFromViewBox(viewBox) {
  const padding = Math.max(viewBox.width, viewBox.height)
  return {
    x: viewBox.x - padding,
    y: viewBox.y - padding,
    width: viewBox.width + padding * 2,
    height: viewBox.height + padding * 2
  }
}

function KnowledgeGraphLayout({
  loading,
  query,
  onQueryChange,
  selectedPaperId,
  onPaperFilterChange,
  selectedSessionId,
  onSessionFilterChange,
  selectedUnitType,
  onUnitTypeFilterChange,
  focusNeighborsOnly,
  onFocusNeighborsToggle,
  expansionDepth,
  onExpansionDepthChange,
  sortMode,
  onSortModeChange,
  unitTypeOptions,
  units,
  edges,
  positions,
  selectedUnit,
  relatedNotes,
  neighboringUnits,
  paperMap,
  sessionMap,
  neighborUnitIds,
  onSelectUnit,
  onOpenNote,
  onOpenSession,
  onMoveUnit,
  onResetLayout
}) {
  const [draggingNodeId, setDraggingNodeId] = useState(null)
  const [filtersExpanded, setFiltersExpanded] = useState(false)
  const [isPanning, setIsPanning] = useState(false)
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT })
  const svgRef = useRef(null)
  const panStateRef = useRef(null)
  const dragStateRef = useRef(null)

  function pointerToSvg(event) {
    if (!svgRef.current) {
      return null
    }
    const rect = svgRef.current.getBoundingClientRect()
    const scaleX = viewBox.width / rect.width
    const scaleY = viewBox.height / rect.height
    return {
      x: viewBox.x + (event.clientX - rect.left) * scaleX,
      y: viewBox.y + (event.clientY - rect.top) * scaleY
    }
  }

  function handlePointerDown(event, unitId) {
    if (event.button !== 0) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    const point = pointerToSvg(event)
    const nodePoint = positions[unitId]
    dragStateRef.current =
      point && nodePoint
        ? {
            startPointerX: point.x,
            startPointerY: point.y,
            startNodeX: nodePoint.x,
            startNodeY: nodePoint.y
          }
        : null
    setDraggingNodeId(unitId)
    onSelectUnit(unitId)
  }

  function handleCanvasPointerDown(event) {
    if (event.button !== 1) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    panStateRef.current = {
      clientX: event.clientX,
      clientY: event.clientY,
      viewBox
    }
    setIsPanning(true)
  }

  function handlePointerMove(event) {
    if (draggingNodeId) {
      const point = pointerToSvg(event)
      const dragState = dragStateRef.current
      if (!point || !dragState) {
        return
      }
      onMoveUnit(draggingNodeId, {
        x: dragState.startNodeX + (point.x - dragState.startPointerX),
        y: dragState.startNodeY + (point.y - dragState.startPointerY)
      })
      return
    }
    if (!panStateRef.current || event.buttons !== 4) {
      return
    }
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) {
      return
    }
    const scaleX = panStateRef.current.viewBox.width / rect.width
    const scaleY = panStateRef.current.viewBox.height / rect.height
    const deltaX = (event.clientX - panStateRef.current.clientX) * scaleX
    const deltaY = (event.clientY - panStateRef.current.clientY) * scaleY
    setViewBox({
      ...panStateRef.current.viewBox,
      x: panStateRef.current.viewBox.x - deltaX,
      y: panStateRef.current.viewBox.y - deltaY
    })
  }

  function handlePointerUp() {
    setDraggingNodeId(null)
    dragStateRef.current = null
    panStateRef.current = null
    setIsPanning(false)
  }

  function handleCanvasClick(event) {
    onSelectUnit(null)
  }

  function handleCanvasWheel(event) {
    if (!svgRef.current) {
      return
    }
    event.preventDefault()
    const point = pointerToSvg(event)
    if (!point) {
      return
    }
    const zoomFactor = event.deltaY > 0 ? 1.12 : 0.9
    const nextWidth = Math.max(MIN_VIEWBOX_WIDTH, Math.min(MAX_VIEWBOX_WIDTH, viewBox.width * zoomFactor))
    const nextHeight = (nextWidth / CANVAS_WIDTH) * CANVAS_HEIGHT
    const ratioX = (point.x - viewBox.x) / viewBox.width
    const ratioY = (point.y - viewBox.y) / viewBox.height

    setViewBox({
      x: point.x - ratioX * nextWidth,
      y: point.y - ratioY * nextHeight,
      width: nextWidth,
      height: nextHeight
    })
  }

  const paperOptions = [...paperMap.values()].sort((left, right) => String(left.title || '').localeCompare(String(right.title || '')))
  const sessionOptions = [...sessionMap.values()].sort((left, right) => left.id - right.id)
  const backgroundRect = backgroundRectFromViewBox(viewBox)
  const unitTypeLanes = [...new Set(units.map((unit) => unit.unit_type || 'concept'))].sort(compareUnitType)
  const laneLabels =
    focusNeighborsOnly && selectedUnit
      ? [
          { key: 'selected', x: 260, label: '当前节点' },
          { key: 'first-hop', x: 580, label: '一跳关联' },
          ...(expansionDepth >= 2 ? [{ key: 'second-hop', x: 860, label: '二跳关联' }] : [])
        ]
      : unitTypeLanes.map((unitType, index) => ({
          key: unitType,
          x: 88 + ((CANVAS_WIDTH - 176) / unitTypeLanes.length) * index + (CANVAS_WIDTH - 176) / unitTypeLanes.length / 2,
          label: unitType
        }))
  const activeFilterLabels = [
    selectedPaperId !== 'all' ? `论文: ${paperMap.get(selectedPaperId)?.title || selectedPaperId}` : null,
    selectedSessionId !== 'all'
      ? `Session: ${sessionMap.get(Number(selectedSessionId))?.name || selectedSessionId}`
      : null,
    selectedUnitType !== 'all' ? `类型: ${selectedUnitType}` : null,
    focusNeighborsOnly ? `${expansionDepth} 跳焦点阅读` : null,
    sortMode !== 'centrality'
      ? `排序: ${sortMode === 'notes' ? '笔记频次' : '名称'}`
      : null
  ].filter(Boolean)

  return (
    <main className="library-page knowledge-page">
      <section className="library-title-row">
        <h1 className="library-title">知识图谱</h1>
        <p className="library-subtitle">一个 knowledge unit 就是一个节点，支持分组阅读、焦点展开、拖拽，以及从节点直接回跳到笔记和论文 Session。</p>
      </section>

      <section className="knowledge-workspace">
        <section className="knowledge-canvas-panel">
          <div className="knowledge-toolbar knowledge-toolbar-main">
            <input
              className="floating-create-input knowledge-search-input"
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="搜索节点、别名或知识摘要"
            />
            <button
              type="button"
              className={`floating-create-btn knowledge-filter-toggle ${filtersExpanded ? 'active' : ''}`}
              onClick={() => setFiltersExpanded((value) => !value)}
            >
              {filtersExpanded ? '收起筛选' : '筛选'}
            </button>
            <div className="knowledge-stats">
              <span>{units.length} 个单元</span>
              <span>{edges.length} 条关系</span>
            </div>
          </div>

          <div className="knowledge-filter-summary">
            {activeFilterLabels.length === 0 ? (
              <span className="knowledge-filter-pill muted">当前无额外筛选</span>
            ) : (
              activeFilterLabels.map((label) => (
                <span key={label} className="knowledge-filter-pill">
                  {label}
                </span>
              ))
            )}
          </div>

          {filtersExpanded ? (
            <div className="knowledge-toolbar knowledge-toolbar-filters">
              <select
                className="floating-create-input notes-select knowledge-filter-select"
                value={selectedPaperId}
                onChange={(event) => onPaperFilterChange(event.target.value)}
              >
                <option value="all">全部论文</option>
                {paperOptions.map((paper) => (
                  <option key={paper.id} value={paper.id}>
                    {paper.title}
                  </option>
                ))}
              </select>
              <select
                className="floating-create-input notes-select knowledge-filter-select"
                value={selectedSessionId}
                onChange={(event) => onSessionFilterChange(event.target.value)}
              >
                <option value="all">全部 Session</option>
                {sessionOptions.map((session) => (
                  <option key={session.id} value={String(session.id)}>
                    #{session.id} {session.name}
                  </option>
                ))}
              </select>
              <select
                className="floating-create-input notes-select knowledge-filter-select"
                value={selectedUnitType}
                onChange={(event) => onUnitTypeFilterChange(event.target.value)}
              >
                {unitTypeOptions.map((unitType) => (
                  <option key={unitType} value={unitType}>
                    {unitType === 'all' ? '全部类型' : unitType}
                  </option>
                ))}
              </select>
              <label className="knowledge-toggle">
                <input
                  type="checkbox"
                  checked={focusNeighborsOnly}
                  onChange={(event) => onFocusNeighborsToggle(event.target.checked)}
                />
                <span>焦点阅读</span>
              </label>
              <select
                className="floating-create-input notes-select knowledge-filter-select"
                value={String(expansionDepth)}
                onChange={(event) => onExpansionDepthChange(Number(event.target.value))}
                disabled={!focusNeighborsOnly}
              >
                <option value="1">一跳展开</option>
                <option value="2">二跳展开</option>
              </select>
              <select
                className="floating-create-input notes-select knowledge-filter-select"
                value={sortMode}
                onChange={(event) => onSortModeChange(event.target.value)}
              >
                <option value="centrality">按中心性</option>
                <option value="notes">按笔记频次</option>
                <option value="alphabetical">按名称</option>
              </select>
              <button type="button" className="floating-create-btn" onClick={onResetLayout}>
                重置布局
              </button>
            </div>
          ) : null}

          {loading ? <div className="library-loading">正在加载知识图谱...</div> : null}

          <div className="knowledge-canvas-shell">
            {units.length === 0 ? (
              <div className="empty-state">当前筛选条件下没有可展示的图谱数据。</div>
            ) : (
              <svg
                ref={svgRef}
                className={`knowledge-canvas ${isPanning ? 'panning' : ''}`}
                viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
                preserveAspectRatio="xMidYMid meet"
                role="img"
                aria-label="知识图谱"
                onPointerDown={handleCanvasPointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerUp}
                onWheel={handleCanvasWheel}
              >
                <rect
                  x={backgroundRect.x}
                  y={backgroundRect.y}
                  width={backgroundRect.width}
                  height={backgroundRect.height}
                  fill="transparent"
                  onClick={handleCanvasClick}
                />
                {laneLabels.map((lane) => (
                  <text key={lane.key} className="knowledge-lane-label" x={lane.x} y={42} textAnchor="middle">
                    {lane.label}
                  </text>
                ))}
                {edges.map((edge) => {
                  const from = positions[edge.from_unit_id]
                  const to = positions[edge.to_unit_id]
                  if (!from || !to) {
                    return null
                  }
                  const active = selectedUnit && edge.from_unit_id === selectedUnit.id
                  const anchorPoint = from
                  const targetPoint = to
                  const labelLayouts =
                    active && selectedUnit
                      ? buildEdgeLabelLayouts(anchorPoint, targetPoint, edge.relations || [edge.relation])
                      : []
                  return (
                    <g key={edge.id} className={active ? 'knowledge-edge active' : 'knowledge-edge'}>
                      <line
                        className="knowledge-edge-line"
                        x1={from.x}
                        y1={from.y}
                        x2={to.x}
                        y2={to.y}
                      />
                      {labelLayouts.map((labelLayout, index) => (
                        <text
                          key={`${edge.id}-${labelLayout.text}-${index}`}
                          className={`knowledge-edge-label ${labelLayout.isCompact ? 'compact' : ''}`}
                          x={labelLayout.x}
                          y={labelLayout.y}
                          transform={`rotate(${labelLayout.angle} ${labelLayout.x} ${labelLayout.y})`}
                          dominantBaseline="middle"
                        >
                          {labelLayout.text}
                        </text>
                      ))}
                    </g>
                  )
                })}

                {units.map((unit) => {
                  const point = positions[unit.id]
                  if (!point) {
                    return null
                  }
                  const active = selectedUnit?.id === unit.id
                  const nearby = neighborUnitIds?.has(unit.id)
                  return (
                    <g
                      key={unit.id}
                      className={`knowledge-node ${active ? 'active' : ''} ${nearby ? 'nearby' : ''}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelectUnit(unit.id)
                      }}
                      onPointerDown={(event) => handlePointerDown(event, unit.id)}
                    >
                      <circle
                        cx={point.x}
                        cy={point.y}
                        r={active ? 24 : nearby ? 20 : 20}
                        fill={unitColor(unit.unit_type)}
                      />
                      <title>{unit.term}</title>
                      <text x={point.x} y={point.y - 28} textAnchor="middle">
                        {formatNodeLabel(unit.term)}
                      </text>
                    </g>
                  )
                })}
              </svg>
            )}
          </div>
        </section>

        <aside className="knowledge-detail-panel">
          {!selectedUnit ? (
            <div className="empty-state">请选择一个单元节点查看详情。</div>
          ) : (
            <>
              <div className="knowledge-detail-header">
                <div>
                  <div className="knowledge-node-type">{selectedUnit.unit_type}</div>
                  <h2>{selectedUnit.term}</h2>
                </div>
                {selectedUnit.aliases?.length ? (
                  <div className="knowledge-aliases">{selectedUnit.aliases.join(' / ')}</div>
                ) : null}
              </div>

              <section className="knowledge-detail-section">
                <h3>单元摘要</h3>
                <article className="knowledge-card">
                  <div className="knowledge-card-title">
                    {selectedUnit.term}
                    <span>{selectedUnit.unit_type}</span>
                  </div>
                  <p>{selectedUnit.summary || selectedUnit.core_claim || '暂无摘要'}</p>
                </article>
              </section>

              <section className="knowledge-detail-section">
                <h3>向外关联单元</h3>
                {neighboringUnits.length === 0 ? (
                  <div className="project-empty">暂无向外关联单元</div>
                ) : (
                  <div className="knowledge-neighbor-list">
                    {neighboringUnits.map((unit) => (
                      <button
                        key={unit.id}
                        type="button"
                        className="knowledge-neighbor-chip"
                        onClick={() => onSelectUnit(unit.id)}
                      >
                        {unit.term}
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="knowledge-detail-section">
                <h3>关联笔记与跳转</h3>
                {relatedNotes.length === 0 ? (
                  <div className="project-empty">暂无关联笔记</div>
                ) : (
                  relatedNotes.map((note) => {
                    const paper = note.paper_id ? paperMap.get(note.paper_id) : null
                    const session = note.session_id ? sessionMap.get(note.session_id) : null

                    return (
                      <article key={note.id} className="knowledge-card">
                        <div className="knowledge-card-title">
                          {note.title}
                          <span>Note #{note.id}</span>
                        </div>
                        <p>{note.summary || '这条笔记包含与当前节点相关的知识单元。'}</p>
                        <div className="knowledge-card-meta">
                          <span>{paper ? paper.title : '未绑定论文'}</span>
                          <span>{session ? `#${session.id} ${session.name}` : '未绑定 Session'}</span>
                        </div>
                        <div className="knowledge-card-actions">
                          <button
                            type="button"
                            className="floating-create-btn"
                            onClick={() => onOpenNote(note.id)}
                          >
                            打开笔记
                          </button>
                          <button
                            type="button"
                            className="floating-create-btn primary"
                            onClick={() => onOpenSession(note)}
                            disabled={!note.paper_id || !note.session_id}
                          >
                            打开 Session
                          </button>
                        </div>
                      </article>
                    )
                  })
                )}
              </section>
            </>
          )}
        </aside>
      </section>
    </main>
  )
}

export default KnowledgeGraphLayout
