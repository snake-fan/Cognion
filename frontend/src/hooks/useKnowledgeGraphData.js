import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchKnowledgeGraph } from '../services/api'

const CANVAS_WIDTH = 1040
const CANVAS_HEIGHT = 720
const UNIT_TYPE_LAYOUT_ORDER = ['claim', 'method', 'question', 'concept']

function aggregateEdges(edges) {
  const grouped = new Map()

  for (const edge of Array.isArray(edges) ? edges : []) {
    const fromId = Number(edge?.from_unit_id)
    const toId = Number(edge?.to_unit_id)
    if (!fromId || !toId || fromId === toId) {
      continue
    }

    const key = `${fromId}:${toId}`
    const relation = String(edge?.relation || 'RELATED_TO')
    const entry = grouped.get(key) || {
      id: key,
      from_unit_id: fromId,
      to_unit_id: toId,
      relations: [],
      relation_set: new Set(),
      raw_edge_ids: []
    }

    if (!entry.relation_set.has(relation)) {
      entry.relation_set.add(relation)
      entry.relations.push(relation)
    }
    if (edge?.id !== undefined && edge?.id !== null) {
      entry.raw_edge_ids.push(edge.id)
    }
    grouped.set(key, entry)
  }

  return [...grouped.values()].map((entry) => ({
    ...entry,
    relation: entry.relations[0] || 'RELATED_TO'
  }))
}

function buildDegreeCountMap(edges) {
  const counts = new Map()
  for (const edge of Array.isArray(edges) ? edges : []) {
    counts.set(edge.from_unit_id, (counts.get(edge.from_unit_id) || 0) + 1)
  }
  return counts
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

function sortUnitsForLayout(units, edges) {
  const degreeCounts = buildDegreeCountMap(edges)
  return [...units].sort((left, right) => {
    const degreeDelta = (degreeCounts.get(right.id) || 0) - (degreeCounts.get(left.id) || 0)
    if (degreeDelta !== 0) {
      return degreeDelta
    }
    const noteDelta = (right.note_ids?.length || 0) - (left.note_ids?.length || 0)
    if (noteDelta !== 0) {
      return noteDelta
    }
    return String(left.term || '').localeCompare(String(right.term || ''))
  })
}

function clampToCanvas(point, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  return {
    x: Math.max(58, Math.min(width - 58, Math.round(point.x))),
    y: Math.max(58, Math.min(height - 58, Math.round(point.y)))
  }
}

function buildInitialUnitPositions(units, edges = [], width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  if (!Array.isArray(units) || units.length === 0) {
    return {}
  }

  const centerX = width / 2
  const centerY = height / 2
  const positions = {}

  if (units.length === 1) {
    positions[units[0].id] = { x: centerX, y: centerY }
    return positions
  }

  const grouped = new Map()
  for (const unit of units) {
    const unitType = String(unit.unit_type || 'concept').toLowerCase()
    const group = grouped.get(unitType) || []
    group.push(unit)
    grouped.set(unitType, group)
  }

  const groups = [...grouped.entries()].sort(([left], [right]) => compareUnitType(left, right))
  const marginX = 88
  const marginTop = 92
  const marginBottom = 80
  const bandWidth = (width - marginX * 2) / groups.length
  const usableHeight = height - marginTop - marginBottom

  groups.forEach(([unitType, groupUnits], groupIndex) => {
    const sortedUnits = sortUnitsForLayout(groupUnits, edges)
    const maxRowsPerColumn = Math.max(1, Math.floor(usableHeight / 76))
    const columnCount = Math.max(1, Math.ceil(sortedUnits.length / maxRowsPerColumn))
    const rowCount = Math.ceil(sortedUnits.length / columnCount)
    const rowGap = rowCount <= 1 ? 0 : Math.min(88, Math.max(62, usableHeight / (rowCount - 1)))
    const columnGap = columnCount <= 1 ? 0 : Math.min(82, Math.max(54, (bandWidth - 74) / (columnCount - 1)))
    const groupCenterX = marginX + bandWidth * groupIndex + bandWidth / 2
    const columnsWidth = (columnCount - 1) * columnGap

    sortedUnits.forEach((unit, index) => {
      const column = Math.floor(index / rowCount)
      const row = index % rowCount
      positions[unit.id] = clampToCanvas(
        {
          x: groupCenterX - columnsWidth / 2 + column * columnGap,
          y: marginTop + row * rowGap
        },
        width,
        height
      )
    })
  })

  return positions
}

function placeFocusedUnits(positions, units, startX, width, height, maxColumns = 2) {
  if (units.length === 0) {
    return
  }

  const top = 92
  const bottom = height - 80
  const columnCount = Math.min(maxColumns, Math.max(1, Math.ceil(units.length / 7)))
  const rowCount = Math.ceil(units.length / columnCount)
  const rowGap = rowCount <= 1 ? 0 : Math.min(86, Math.max(58, (bottom - top) / (rowCount - 1)))
  const columnGap = columnCount <= 1 ? 0 : 116
  const totalHeight = (rowCount - 1) * rowGap
  const startY = height / 2 - totalHeight / 2

  units.forEach((unit, index) => {
    const column = Math.floor(index / rowCount)
    const row = index % rowCount
    positions[unit.id] = clampToCanvas(
      {
        x: startX + column * columnGap,
        y: startY + row * rowGap
      },
      width,
      height
    )
  })
}

function buildFocusedUnitPositions(units, edges, selectedUnit, expansionDepth, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  if (!selectedUnit) {
    return buildInitialUnitPositions(units, edges, width, height)
  }

  const unitMap = new Map(units.map((unit) => [unit.id, unit]))
  const firstHopIds = new Set()
  const secondHopIds = new Set()

  for (const edge of edges) {
    if (edge.from_unit_id === selectedUnit.id && unitMap.has(edge.to_unit_id)) {
      firstHopIds.add(edge.to_unit_id)
    }
  }

  if (expansionDepth >= 2) {
    for (const edge of edges) {
      if (firstHopIds.has(edge.from_unit_id) && unitMap.has(edge.to_unit_id) && edge.to_unit_id !== selectedUnit.id) {
        secondHopIds.add(edge.to_unit_id)
      }
    }
  }

  const sortedUnits = sortUnitsForLayout(units, edges)
  const firstHopUnits = sortedUnits.filter((unit) => firstHopIds.has(unit.id))
  const secondHopUnits = sortedUnits.filter((unit) => secondHopIds.has(unit.id) && !firstHopIds.has(unit.id))
  const otherUnits = sortedUnits.filter(
    (unit) => unit.id !== selectedUnit.id && !firstHopIds.has(unit.id) && !secondHopIds.has(unit.id)
  )
  const positions = {
    [selectedUnit.id]: { x: 260, y: height / 2 }
  }

  placeFocusedUnits(positions, firstHopUnits, 520, width, height, 2)
  placeFocusedUnits(positions, secondHopUnits, 800, width, height, 2)
  placeFocusedUnits(positions, otherUnits, 930, width, height, 1)

  return positions
}

function clampPoint(point) {
  return clampToCanvas(point)
}

function useKnowledgeGraphData({ isActive = false } = {}) {
  const [loading, setLoading] = useState(false)
  const [graph, setGraph] = useState({
    units: [],
    edges: [],
    notes: [],
    papers: [],
    sessions: []
  })
  const [query, setQuery] = useState('')
  const [selectedUnitId, setSelectedUnitId] = useState(null)
  const [selectedPaperId, setSelectedPaperId] = useState('all')
  const [selectedSessionId, setSelectedSessionId] = useState('all')
  const [selectedUnitType, setSelectedUnitType] = useState('all')
  const [focusNeighborsOnly, setFocusNeighborsOnly] = useState(false)
  const [expansionDepth, setExpansionDepth] = useState(1)
  const [sortMode, setSortMode] = useState('centrality')
  const [positions, setPositions] = useState({})
  const [refreshToken, setRefreshToken] = useState(0)
  const lastAutoLayoutKeyRef = useRef('')

  useEffect(() => {
    if (!isActive) {
      return undefined
    }

    let cancelled = false

    async function loadGraph() {
      setLoading(true)
      try {
        const payload = await fetchKnowledgeGraph()
        if (cancelled) {
          return
        }
        const nextGraph = {
          units: payload.units || [],
          edges: aggregateEdges(payload.edges || []),
          notes: payload.notes || [],
          papers: payload.papers || [],
          sessions: payload.sessions || []
        }
        setGraph(nextGraph)
        setPositions((prev) => {
          const seeded = buildInitialUnitPositions(nextGraph.units, nextGraph.edges)
          const next = { ...seeded, ...prev }
          for (const unit of nextGraph.units) {
            if (!next[unit.id]) {
              next[unit.id] = seeded[unit.id]
            }
          }
          return next
        })
      } catch (error) {
        console.error(error)
        if (cancelled) {
          return
        }
        setGraph({
          units: [],
          edges: [],
          notes: [],
          papers: [],
          sessions: []
        })
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadGraph()
    return () => {
      cancelled = true
    }
  }, [isActive, refreshToken])

  useEffect(() => {
    function handleKnowledgeGraphRefresh() {
      setRefreshToken((value) => value + 1)
    }

    window.addEventListener('cognion:notes-updated', handleKnowledgeGraphRefresh)
    window.addEventListener('cognion:knowledge-graph-refresh', handleKnowledgeGraphRefresh)
    return () => {
      window.removeEventListener('cognion:notes-updated', handleKnowledgeGraphRefresh)
      window.removeEventListener('cognion:knowledge-graph-refresh', handleKnowledgeGraphRefresh)
    }
  }, [])

  const paperMap = useMemo(() => new Map(graph.papers.map((paper) => [paper.id, paper])), [graph.papers])
  const sessionMap = useMemo(() => new Map(graph.sessions.map((session) => [session.id, session])), [graph.sessions])
  const noteMap = useMemo(() => new Map(graph.notes.map((note) => [note.id, note])), [graph.notes])

  const unitContexts = useMemo(() => {
    const contexts = new Map()
    for (const unit of graph.units) {
      const noteIds = new Set(unit.note_ids || [])
      const paperIds = new Set()
      const sessionIds = new Set()

      for (const noteId of noteIds) {
        const note = noteMap.get(noteId)
        if (!note) {
          continue
        }
        if (note.paper_id) {
          paperIds.add(note.paper_id)
        }
        if (note.session_id) {
          sessionIds.add(String(note.session_id))
        }
      }

      contexts.set(unit.id, {
        noteIds,
        paperIds,
        sessionIds
      })
    }
    return contexts
  }, [graph.units, noteMap])

  const filteredUnits = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    return graph.units.filter((unit) => {
      const context = unitContexts.get(unit.id)
      if (selectedUnitType !== 'all' && unit.unit_type !== selectedUnitType) {
        return false
      }
      if (selectedPaperId !== 'all' && !context?.paperIds?.has(selectedPaperId)) {
        return false
      }
      if (selectedSessionId !== 'all' && !context?.sessionIds?.has(String(selectedSessionId))) {
        return false
      }
      if (!trimmed) {
        return true
      }

      const haystacks = [
        unit.term,
        unit.summary,
        unit.core_claim,
        unit.canonical_key,
        ...(Array.isArray(unit.aliases) ? unit.aliases : [])
      ]
      return haystacks.some((text) => String(text || '').toLowerCase().includes(trimmed))
    })
  }, [graph.units, query, selectedPaperId, selectedSessionId, selectedUnitType, unitContexts])

  const baseVisibleUnitIds = useMemo(() => new Set(filteredUnits.map((unit) => unit.id)), [filteredUnits])

  const selectedUnit =
    filteredUnits.find((unit) => unit.id === selectedUnitId) ||
    graph.units.find((unit) => unit.id === selectedUnitId) ||
    null

  useEffect(() => {
    if (selectedUnitId !== null && !selectedUnit) {
      setSelectedUnitId(null)
    }
  }, [selectedUnit, selectedUnitId])

  const neighborUnitIds = useMemo(() => {
    if (!selectedUnit) {
      return new Set()
    }
    const neighbors = new Set([selectedUnit.id])
    for (const edge of graph.edges) {
      if (edge.from_unit_id === selectedUnit.id) {
        neighbors.add(edge.to_unit_id)
      }
    }
    return neighbors
  }, [graph.edges, selectedUnit])

  const secondHopUnitIds = useMemo(() => {
    if (!selectedUnit) {
      return new Set()
    }

    const firstHopUnitIds = new Set(neighborUnitIds)
    const neighbors = new Set(firstHopUnitIds)
    for (const edge of graph.edges) {
      if (firstHopUnitIds.has(edge.from_unit_id)) {
        neighbors.add(edge.to_unit_id)
      }
    }
    return neighbors
  }, [graph.edges, neighborUnitIds, selectedUnit])

  const degreeMap = useMemo(() => {
    const next = new Map()
    for (const edge of graph.edges) {
      next.set(edge.from_unit_id, (next.get(edge.from_unit_id) || 0) + 1)
    }
    return next
  }, [graph.edges])

  const noteCountMap = useMemo(() => {
    const next = new Map()
    for (const unit of graph.units) {
      const context = unitContexts.get(unit.id)
      next.set(unit.id, context?.noteIds?.size || 0)
    }
    return next
  }, [graph.units, unitContexts])

  const visibleUnitIds = useMemo(() => {
    if (!focusNeighborsOnly || !selectedUnit) {
      return baseVisibleUnitIds
    }
    const next = new Set()
    const expandedSet = expansionDepth >= 2 ? secondHopUnitIds : neighborUnitIds
    for (const unitId of expandedSet) {
      if (baseVisibleUnitIds.has(unitId)) {
        next.add(unitId)
      }
    }
    return next
  }, [baseVisibleUnitIds, expansionDepth, focusNeighborsOnly, neighborUnitIds, secondHopUnitIds, selectedUnit])

  const units = useMemo(
    () =>
      filteredUnits
        .filter((unit) => visibleUnitIds.has(unit.id))
        .sort((left, right) => {
          if (sortMode === 'notes') {
            return (noteCountMap.get(right.id) || 0) - (noteCountMap.get(left.id) || 0)
          }
          if (sortMode === 'alphabetical') {
            return String(left.term || '').localeCompare(String(right.term || ''))
          }
          return (degreeMap.get(right.id) || 0) - (degreeMap.get(left.id) || 0)
        }),
    [degreeMap, filteredUnits, noteCountMap, sortMode, visibleUnitIds]
  )

  const edges = useMemo(
    () =>
      graph.edges.filter((edge) => {
        if (!visibleUnitIds.has(edge.from_unit_id) || !visibleUnitIds.has(edge.to_unit_id)) {
          return false
        }
        if (focusNeighborsOnly && selectedUnit) {
          if (edge.to_unit_id === selectedUnit.id) {
            return false
          }
          return edge.from_unit_id === selectedUnit.id || (expansionDepth >= 2 && neighborUnitIds.has(edge.from_unit_id))
        }
        return true
      }),
    [expansionDepth, focusNeighborsOnly, graph.edges, neighborUnitIds, selectedUnit, visibleUnitIds]
  )

  useEffect(() => {
    if (!focusNeighborsOnly || !selectedUnit || units.length === 0) {
      return
    }

    const layoutKey = [
      'focus',
      selectedUnit.id,
      expansionDepth,
      units.map((unit) => unit.id).join(','),
      edges.map((edge) => edge.id).join(',')
    ].join(':')

    if (lastAutoLayoutKeyRef.current === layoutKey) {
      return
    }

    lastAutoLayoutKeyRef.current = layoutKey
    setPositions((prev) => ({
      ...prev,
      ...buildFocusedUnitPositions(units, edges, selectedUnit, expansionDepth)
    }))
  }, [edges, expansionDepth, focusNeighborsOnly, selectedUnit, units])

  useEffect(() => {
    if (focusNeighborsOnly || !lastAutoLayoutKeyRef.current.startsWith('focus:')) {
      return
    }

    lastAutoLayoutKeyRef.current = ''
    setPositions(buildInitialUnitPositions(graph.units, graph.edges))
  }, [focusNeighborsOnly, graph.edges, graph.units])

  const relatedNotes = useMemo(() => {
    if (!selectedUnit?.note_ids?.length) {
      return []
    }
    return selectedUnit.note_ids.map((noteId) => noteMap.get(noteId)).filter(Boolean)
  }, [noteMap, selectedUnit])

  const neighboringUnits = useMemo(() => {
    if (!selectedUnit) {
      return []
    }
    return [...neighborUnitIds]
      .filter((unitId) => unitId !== selectedUnit.id)
      .map((unitId) => graph.units.find((unit) => unit.id === unitId))
      .filter(Boolean)
      .slice(0, 12)
  }, [graph.units, neighborUnitIds, selectedUnit])

  const unitTypeOptions = useMemo(
    () => ['all', ...new Set(graph.units.map((unit) => unit.unit_type).filter(Boolean))],
    [graph.units]
  )

  function moveUnit(unitId, point) {
    setPositions((prev) => ({
      ...prev,
      [unitId]: clampPoint(point)
    }))
  }

  function resetLayout() {
    if (focusNeighborsOnly && selectedUnit) {
      setPositions((prev) => ({
        ...prev,
        ...buildFocusedUnitPositions(units, edges, selectedUnit, expansionDepth)
      }))
      return
    }
    setPositions(buildInitialUnitPositions(graph.units, graph.edges))
  }

  function refreshGraph() {
    setRefreshToken((value) => value + 1)
  }

  return {
    loading,
    query,
    setQuery,
    selectedPaperId,
    setSelectedPaperId,
    selectedSessionId,
    setSelectedSessionId,
    selectedUnitType,
    setSelectedUnitType,
    focusNeighborsOnly,
    setFocusNeighborsOnly,
    expansionDepth,
    setExpansionDepth,
    sortMode,
    setSortMode,
    unitTypeOptions,
    units,
    edges,
    selectedUnit,
    relatedNotes,
    neighboringUnits,
    paperMap,
    sessionMap,
    positions,
    neighborUnitIds,
    moveUnit,
    resetLayout,
    refreshGraph,
    onSelectUnit: setSelectedUnitId
  }
}

export default useKnowledgeGraphData
