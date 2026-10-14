import { useEffect, useRef, useState, useCallback } from 'react';
import type { InvestigationState, AgentType, InvestigationStatus } from '../types';

interface WSMessage {
  type: string;
  update_type?: string;
  investigation_id: string;
  data: any;
  timestamp: string;
}

export interface LiveInvestigationEvent {
  update_type: string;
  data: Record<string, any>;
  timestamp: string;
}

interface AgentThinkingData {
  agent_type: string;
  status: 'started' | 'thinking' | 'completed';
  reasoning?: string;
}

interface RoutingDecisionData {
  selected_agent: string;
  reasoning: string;
  iteration: number;
}

interface AgentFindingData {
  agent_type: string;
  finding: {
    hypothesis: string;
    finding: string;
    confidence: number;
    reasoning: string;
    evidence: string[];
  };
}

interface ProgressData {
  iteration: number;
  max_iterations: number;
  overall_confidence: number;
  progress_percent: number;
}

interface InitialStateData {
  status: string;
  iteration: number;
  max_iterations: number;
  overall_confidence: number;
  current_agent: string | null;
  agents_invoked: string[];
  evidence_gaps: string[];
}

export function useInvestigationWS(investigationId: string | undefined) {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [agentThinking, setAgentThinking] = useState<AgentThinkingData | null>(null);
  const [routingDecision, setRoutingDecision] = useState<RoutingDecisionData | null>(null);
  const [agentFinding, setAgentFinding] = useState<AgentFindingData | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [initialState, setInitialState] = useState<InitialStateData | null>(null);
  const [status, setStatus] = useState<InvestigationStatus>('pending');
  const [liveEvents, setLiveEvents] = useState<LiveInvestigationEvent[]>([]);
  
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;

  const connect = useCallback(() => {
    if (!investigationId) return;
    
    const apiBaseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = new URL(`/api/investigations/${encodeURIComponent(investigationId)}/ws`, apiBaseUrl);
    wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const websocket = new WebSocket(wsUrl.toString());
    
    websocket.onopen = () => {
      console.log(`WebSocket connected for investigation ${investigationId}`);
      setConnected(true);
      setWs(websocket);
      reconnectAttemptsRef.current = 0;
    };
    
    websocket.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);
        setLastMessage(message);
        
        switch (message.type) {
          case 'initial_state':
            if (message.data) {
              setInitialState(message.data);
              setStatus(message.data.status as InvestigationStatus);
            }
            break;
            
          case 'investigation_update':
            if (!message.update_type || !message.data) break;
            setLiveEvents(events => [
              {
                update_type: message.update_type!,
                data: message.data,
                timestamp: message.timestamp || new Date().toISOString(),
              },
              ...events,
            ].slice(0, 20));
            
            switch (message.update_type) {
              case 'agent_thinking':
                setAgentThinking(message.data);
                break;
              case 'routing_decision':
                setRoutingDecision(message.data);
                break;
              case 'agent_finding':
                setAgentFinding(message.data);
                break;
              case 'progress':
                setProgress(message.data);
                break;
              case 'status_change':
                if (message.data && message.data.status) {
                  setStatus(message.data.status as InvestigationStatus);
                }
                break;
            }
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };
    
    websocket.onclose = () => {
      console.log(`WebSocket disconnected for investigation ${investigationId}`);
      setConnected(false);
      setWs(null);
      
      // Attempt reconnection
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current++;
          console.log(`Reconnecting... attempt ${reconnectAttemptsRef.current}`);
          connect();
        }, delay);
      }
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [investigationId]);

  useEffect(() => {
    if (!investigationId) return;
    
    connect();
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (ws) {
        ws.close();
      }
    };
  }, [investigationId, connect]);

  const sendPing = useCallback(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, [ws]);

  // Send ping every 30 seconds to keep connection alive
  useEffect(() => {
    if (!connected) return;
    const interval = setInterval(sendPing, 30000);
    return () => clearInterval(interval);
  }, [connected, sendPing]);

  return {
    connected,
    lastMessage,
    agentThinking,
    routingDecision,
    agentFinding,
    progress,
    initialState,
    liveEvents,
    status,
    connect,
    disconnect: () => ws?.close(),
  };
}

export function useInvestigationRealtime(investigationId: string | undefined) {
  const wsData = useInvestigationWS(investigationId);
  
  // Merge WebSocket real-time data with base investigation state
  const getRealtimeInvestigation = useCallback((baseInvestigation: InvestigationState | null): InvestigationState | null => {
    if (!baseInvestigation) return null;
    
    // Create a merged investigation with real-time updates
    const merged = { ...baseInvestigation };
    
    // Update status from WebSocket
    if (wsData.status) {
      merged.investigation_status = wsData.status as InvestigationStatus;
    }
    
    // Update progress from WebSocket
    if (wsData.progress) {
      merged.iteration_count = wsData.progress.iteration;
      merged.overall_confidence = wsData.progress.overall_confidence;
    }
    
    // Update current agent from WebSocket
    if (wsData.agentThinking) {
      // merged.current_agent = wsData.agentThinking.agent_type as AgentType;
      // current_agent not in InvestigationState type, skipping
    }
    
    // Update agents invoked from initial state
    if (wsData.initialState && wsData.initialState.agents_invoked) {
      merged.agents_invoked = wsData.initialState.agents_invoked as AgentType[];
    }
    
    // Update evidence gaps from initial state
    if (wsData.initialState && wsData.initialState.evidence_gaps) {
      merged.evidence_gaps = wsData.initialState.evidence_gaps;
    }
    
    return merged;
  }, [wsData]);
  
  return {
    ...wsData,
    getRealtimeInvestigation,
  };
}
