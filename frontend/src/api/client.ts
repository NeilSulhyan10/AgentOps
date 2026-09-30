import axios from 'axios';
import type {
  Incident,
  InvestigationState,
  InvestigationStatusResponse,
  RootCauseAnalysis,
  RemediationRecommendation,
  TimelineEntry
} from '../types';

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

export default api;