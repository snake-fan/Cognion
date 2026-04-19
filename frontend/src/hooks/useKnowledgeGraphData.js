import { useEffect, useMemo, useState } from 'react'
import { fetchKnowledgeGraph } from '../services/api'

const CANVAS_WIDTH = 1040
const CANVAS_HEIGHT = 720

function aggregateEdges(edges) {
  const grouped = new Map()

  for (const edge of Array.isArray(edges) ? edges : []) {
    const fromId = Number(edge?.from_unit_id)
    const toId = Number(edge?.to_unit_id)
    if (!fromId || !toId || fromId === toId) {
      continue
    }

    const leftId = Math.min(fromId, toId)
    const rightId = Math.max(fromId, toId)
    const key = `${leftId}:${rightId}`
    const relation = String(edge?.relation || 'RELATED_TO')
    const entry = grouped.get(key) || {
      id: key,
      from_unit_id: leftId,
      to_unit_id: rightId,
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

function buildInitialUnitPositions(units, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  if (!Array.isArray(units) || units.length === 0) {
    return {}
  }

  const centerX = width / 2
  const centerY = height / 2
  const total = units.length
  const positions = {}

  if (total === 1) {
    positions[units[0].id] = { x: centerX, y: centerY }
    return positions
  }

  const rings = Math.max(1, Math.ceil(total / 12))
  units.forEach((unit, index) => {
    const ring = index % rings
    const radius = 120 + ring * 92
    const angle = (index / total) * Math.PI * 2 - Math.PI / 2
    positions[unit.id] = {
      x: Math.round(centerX + Math.cos(angle) * radius),
      y: Math.round(centerY + Math.sin(angle) * radius)
    }
  })

  return positions
}

function clampPoint(point) {
  return {
    x: Math.max(58, Math.min(CANVAS_WIDTH - 58, Math.round(point.x))),
    y: Math.max(58, Math.min(CANVAS_HEIGHT - 58, Math.round(point.y)))
  }
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
          const seeded = buildInitialUnitPositions(nextGraph.units)
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
      if (edge.to_unit_id === selectedUnit.id) {
        neighbors.add(edge.from_unit_id)
      }
    }
    return neighbors
  }, [graph.edges, selectedUnit])

  const secondHopUnitIds = useMemo(() => {
    if (!selectedUnit) {
      return new Set()
    }

    const neighbors = new Set(neighborUnitIds)
    for (const edge of graph.edges) {
      if (neighbors.has(edge.from_unit_id)) {
        neighbors.add(edge.to_unit_id)
      }
      if (neighbors.has(edge.to_unit_id)) {
        neighbors.add(edge.from_unit_id)
      }
    }
    return neighbors
  }, [graph.edges, neighborUnitIds, selectedUnit])

  const degreeMap = useMemo(() => {
    const next = new Map()
    for (const edge of graph.edges) {
      next.set(edge.from_unit_id, (next.get(edge.from_unit_id) || 0) + 1)
      next.set(edge.to_unit_id, (next.get(edge.to_unit_id) || 0) + 1)
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
    () => graph.edges.filter((edge) => visibleUnitIds.has(edge.from_unit_id) && visibleUnitIds.has(edge.to_unit_id)),
    [graph.edges, visibleUnitIds]
  )

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
    setPositions(buildInitialUnitPositions(graph.units))
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
