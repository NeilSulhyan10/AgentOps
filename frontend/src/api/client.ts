import axios from 'axios';
import type {
  Incident,
  InvestigationState,
  InvestigationStatusResponse,
  RootCauseAnalysis,
  RemediationRecommendation,
  TimelineEntry
} from '../types';
import type { AgentInfo, FlowTrace, Spawnable } from '../types/flow';
import type { AppPage, AppSummary, Run } from '../types/apps';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const incidentApi = {
  create: async (incident: Omit<Incident, 'started_at' | 'detected_at' | 'metadata' | 'tags'>): Promise<InvestigationStatusResponse> => {
    const response = await api.post<InvestigationStatusResponse>('/api/incidents', { incident });
    return response.data;
  },

  list: async (status?: string): Promise<InvestigationStatusResponse[]> => {
    const params = status ? { status_filter: status } : {};
    const response = await api.get<InvestigationStatusResponse[]>('/api/incidents', { params });
    return response.data;
  },

  get: async (incidentId: string): Promise<InvestigationStatusResponse> => {
    const response = await api.get<InvestigationStatusResponse>(`/api/incidents/${incidentId}`);
    return response.data;
  },

  deleteInvestigation: async (investigationId: string): Promise<void> => {
    await api.delete(`/api/investigations/${investigationId}`);
  },
};

export const investigationApi = {
  get: async (investigationId: string): Promise<InvestigationState> => {
    const response = await api.get<InvestigationState>(`/api/investigations/${investigationId}`);
    return response.data;
  },

  getTimeline: async (investigationId: string): Promise<{ timeline: TimelineEntry[] }> => {
    const response = await api.get(`/api/investigations/${investigationId}/timeline`);
    return response.data;
  },

  getEvidence: async (investigationId: string): Promise<{ evidence: any[] }> => {
    const response = await api.get(`/api/investigations/${investigationId}/evidence`);
    return response.data;
  },

  getRootCause: async (investigationId: string): Promise<RootCauseAnalysis> => {
    const response = await api.get<RootCauseAnalysis>(`/api/investigations/${investigationId}/root-cause`);
    return response.data;
  },

  getRemediation: async (investigationId: string): Promise<RemediationRecommendation> => {
    const response = await api.get<RemediationRecommendation>(`/api/investigations/${investigationId}/remediation`);
    return response.data;
  },
};

export const flowApi = {
  get: async (investigationId: string): Promise<FlowTrace> => {
    const response = await api.get<FlowTrace>(`/api/investigations/${investigationId}/flow`);
    return response.data;
  },
};

export const agentApi = {
  list: async (): Promise<{ specialists: AgentInfo[]; spawnable: Spawnable[] }> => {
    const response = await api.get('/api/agents');
    return response.data;
  },

  create: async (agent: {
    name: string; description: string; layer: string; hypothesis: string; evidence_types: string[]; keywords: string[];
  }): Promise<{ name: string; path: string }> => {
    const response = await api.post('/api/agents', agent);
    return response.data;
  },
};

export const appApi = {
  list: async (): Promise<AppSummary[]> => (await api.get('/api/apps')).data.apps,

  get: async (appKey: string): Promise<AppPage> => (await api.get(`/api/apps/${appKey}`)).data,

  runs: async (incidentId: string): Promise<{ expected_root_cause: string | null; runs: Run[] }> =>
    (await api.get(`/api/incidents/${incidentId}/runs`)).data,

  /** Start a scenario again. Earlier runs are kept; this adds a new one. */
  investigate: async (scenarioId: string): Promise<{ investigation_id: string }> =>
    (await api.post(`/api/scenarios/${scenarioId}/trigger`)).data,

  /** Re-run the incident of an existing investigation (works for live incidents too). */
  rerun: async (investigationId: string): Promise<{ investigation_id: string }> =>
    (await api.post(`/api/investigations/${investigationId}/rerun`)).data,
};

export default api;
