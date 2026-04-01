import { useEffect, useMemo, useState } from 'react'
import { fetchKnowledgeGraph } from '../services/api'

const CANVAS_WIDTH = 1040
const CANVAS_HEIGHT = 720
function aggregateEdges(edges) {
  const grouped = new Map()

  for (const edge of Array.isArray(edges) ? edges : []) {
    const fromId = Number(edge?.from_node_id)
    const toId = Number(edge?.to_node_id)
    if (!fromId || !toId || fromId === toId) {
      continue
    }

    const leftId = Math.min(fromId, toId)
    const rightId = Math.max(fromId, toId)
    const key = `${leftId}:${rightId}`
    const relation = String(edge?.relation || 'RELATED_TO')
    const entry = grouped.get(key) || {
      id: key,
      from_node_id: leftId,
      to_node_id: rightId,
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

function buildInitialNodePositions(nodes, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return {}
  }

  const centerX = width / 2
  const centerY = height / 2
  const total = nodes.length
  const positions = {}

  if (total === 1) {
    positions[nodes[0].id] = { x: centerX, y: centerY }
    return positions
  }

  const rings = Math.max(1, Math.ceil(total / 12))
  nodes.forEach((node, index) => {
    const ring = index % rings
    const radius = 120 + ring * 92
    const angle = (index / total) * Math.PI * 2 - Math.PI / 2
    positions[node.id] = {
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

function useKnowledgeGraphData() {
  const [loading, setLoading] = useState(false)
  const [graph, setGraph] = useState({
    nodes: [],
    edges: [],
    knowledge_units: [],
    notes: [],
    papers: [],
    sessions: []
  })
  const [query, setQuery] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [selectedPaperId, setSelectedPaperId] = useState('all')
  const [selectedSessionId, setSelectedSessionId] = useState('all')
  const [selectedNodeType, setSelectedNodeType] = useState('all')
  const [focusNeighborsOnly, setFocusNeighborsOnly] = useState(false)
  const [expansionDepth, setExpansionDepth] = useState(1)
  const [sortMode, setSortMode] = useState('centrality')
  const [positions, setPositions] = useState({})

  useEffect(() => {
    async function loadGraph() {
      setLoading(true)
      try {
        const payload = await fetchKnowledgeGraph()
        const nextGraph = {
          nodes: payload.nodes || [],
          edges: aggregateEdges(payload.edges || []),
          knowledge_units: payload.knowledge_units || [],
          notes: payload.notes || [],
          papers: payload.papers || [],
          sessions: payload.sessions || []
        }
        setGraph(nextGraph)
        setPositions((prev) => {
          const seeded = buildInitialNodePositions(nextGraph.nodes)
          const next = { ...seeded, ...prev }
          for (const node of nextGraph.nodes) {
            if (!next[node.id]) {
              next[node.id] = seeded[node.id]
            }
          }
          return next
        })
      } catch (error) {
        console.error(error)
        setGraph({
          nodes: [],
          edges: [],
          knowledge_units: [],
          notes: [],
          papers: [],
          sessions: []
        })
      } finally {
        setLoading(false)
      }
    }

    loadGraph()
  }, [])

  const paperMap = useMemo(() => new Map(graph.papers.map((paper) => [paper.id, paper])), [graph.papers])
  const sessionMap = useMemo(() => new Map(graph.sessions.map((session) => [session.id, session])), [graph.sessions])
  const noteMap = useMemo(() => new Map(graph.notes.map((note) => [note.id, note])), [graph.notes])
  const unitMap = useMemo(() => new Map(graph.knowledge_units.map((unit) => [unit.id, unit])), [graph.knowledge_units])

  const nodeContexts = useMemo(() => {
    const contexts = new Map()
    for (const node of graph.nodes) {
      const noteIds = new Set()
      const paperIds = new Set()
      const sessionIds = new Set()

      for (const unitId of node.knowledge_unit_ids || []) {
        const unit = unitMap.get(unitId)
        if (!unit) {
          continue
        }

        for (const noteId of unit.note_ids || []) {
          noteIds.add(noteId)
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
      }

      contexts.set(node.id, {
        noteIds,
        paperIds,
        sessionIds
      })
    }
    return contexts
  }, [graph.nodes, noteMap, unitMap])

  const filteredNodes = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    return graph.nodes.filter((node) => {
      const context = nodeContexts.get(node.id)
      if (selectedNodeType !== 'all' && node.node_type !== selectedNodeType) {
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
        node.name,
        ...(Array.isArray(node.aliases) ? node.aliases : []),
        ...(Array.isArray(node.knowledge_unit_ids)
          ? node.knowledge_unit_ids.map((id) => unitMap.get(id)?.summary || '')
          : [])
      ]
      return haystacks.some((text) => String(text || '').toLowerCase().includes(trimmed))
    })
  }, [graph.nodes, nodeContexts, query, selectedNodeType, selectedPaperId, selectedSessionId, unitMap])

  const baseVisibleNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes])

  const selectedNode =
    filteredNodes.find((node) => node.id === selectedNodeId) ||
    graph.nodes.find((node) => node.id === selectedNodeId) ||
    null

  useEffect(() => {
    if (selectedNodeId !== null && !selectedNode) {
      setSelectedNodeId(null)
    }
  }, [selectedNode, selectedNodeId])

  const neighborNodeIds = useMemo(() => {
    if (!selectedNode) {
      return new Set()
    }
    const neighbors = new Set([selectedNode.id])
    for (const edge of graph.edges) {
      if (edge.from_node_id === selectedNode.id) {
        neighbors.add(edge.to_node_id)
      }
      if (edge.to_node_id === selectedNode.id) {
        neighbors.add(edge.from_node_id)
      }
    }
    return neighbors
  }, [graph.edges, selectedNode])

  const secondHopNodeIds = useMemo(() => {
    if (!selectedNode) {
      return new Set()
    }

    const neighbors = new Set(neighborNodeIds)
    for (const edge of graph.edges) {
      if (neighbors.has(edge.from_node_id)) {
        neighbors.add(edge.to_node_id)
      }
      if (neighbors.has(edge.to_node_id)) {
        neighbors.add(edge.from_node_id)
      }
    }
    return neighbors
  }, [graph.edges, neighborNodeIds, selectedNode])

  const degreeMap = useMemo(() => {
    const next = new Map()
    for (const edge of graph.edges) {
      next.set(edge.from_node_id, (next.get(edge.from_node_id) || 0) + 1)
      next.set(edge.to_node_id, (next.get(edge.to_node_id) || 0) + 1)
    }
    return next
  }, [graph.edges])

  const noteCountMap = useMemo(() => {
    const next = new Map()
    for (const node of graph.nodes) {
      const context = nodeContexts.get(node.id)
      next.set(node.id, context?.noteIds?.size || 0)
    }
    return next
  }, [graph.nodes, nodeContexts])

  const visibleNodeIds = useMemo(() => {
    if (!focusNeighborsOnly || !selectedNode) {
      return baseVisibleNodeIds
    }
    const next = new Set()
    const expandedSet = expansionDepth >= 2 ? secondHopNodeIds : neighborNodeIds
    for (const nodeId of expandedSet) {
      if (baseVisibleNodeIds.has(nodeId)) {
        next.add(nodeId)
      }
    }
    return next
  }, [baseVisibleNodeIds, expansionDepth, focusNeighborsOnly, neighborNodeIds, secondHopNodeIds, selectedNode])

  const nodes = useMemo(
    () =>
      filteredNodes
        .filter((node) => visibleNodeIds.has(node.id))
        .sort((left, right) => {
          if (sortMode === 'notes') {
            return (noteCountMap.get(right.id) || 0) - (noteCountMap.get(left.id) || 0)
          }
          if (sortMode === 'alphabetical') {
            return String(left.name || '').localeCompare(String(right.name || ''))
          }
          return (degreeMap.get(right.id) || 0) - (degreeMap.get(left.id) || 0)
        }),
    [degreeMap, filteredNodes, noteCountMap, sortMode, visibleNodeIds]
  )

  const edges = useMemo(
    () => graph.edges.filter((edge) => visibleNodeIds.has(edge.from_node_id) && visibleNodeIds.has(edge.to_node_id)),
    [graph.edges, visibleNodeIds]
  )

  const selectedKnowledgeUnits = useMemo(() => {
    if (!selectedNode?.knowledge_unit_ids?.length) {
      return []
    }
    return selectedNode.knowledge_unit_ids.map((unitId) => unitMap.get(unitId)).filter(Boolean)
  }, [selectedNode, unitMap])

  const relatedNotes = useMemo(() => {
    const collected = []
    const seen = new Set()
    for (const unit of selectedKnowledgeUnits) {
      for (const noteId of unit.note_ids || []) {
        if (seen.has(noteId)) {
          continue
        }
        const note = noteMap.get(noteId)
        if (!note) {
          continue
        }
        seen.add(noteId)
        collected.push(note)
      }
    }
    return collected
  }, [selectedKnowledgeUnits, noteMap])

  const neighboringNodes = useMemo(() => {
    if (!selectedNode) {
      return []
    }
    return [...neighborNodeIds]
      .filter((nodeId) => nodeId !== selectedNode.id)
      .map((nodeId) => graph.nodes.find((node) => node.id === nodeId))
      .filter(Boolean)
      .slice(0, 12)
  }, [graph.nodes, neighborNodeIds, selectedNode])

  const nodeTypeOptions = useMemo(
    () => ['all', ...new Set(graph.nodes.map((node) => node.node_type).filter(Boolean))],
    [graph.nodes]
  )

  function moveNode(nodeId, point) {
    setPositions((prev) => ({
      ...prev,
      [nodeId]: clampPoint(point)
    }))
  }

  function resetLayout() {
    setPositions(buildInitialNodePositions(graph.nodes))
  }

  return {
    loading,
    query,
    setQuery,
    selectedPaperId,
    setSelectedPaperId,
    selectedSessionId,
    setSelectedSessionId,
    selectedNodeType,
    setSelectedNodeType,
    focusNeighborsOnly,
    setFocusNeighborsOnly,
    expansionDepth,
    setExpansionDepth,
    sortMode,
    setSortMode,
    nodeTypeOptions,
    nodes,
    edges,
    selectedNode,
    selectedKnowledgeUnits,
    relatedNotes,
    neighboringNodes,
    paperMap,
    sessionMap,
    positions,
    neighborNodeIds,
    moveNode,
    resetLayout,
    onSelectNode: setSelectedNodeId
  }
}

export default useKnowledgeGraphData
