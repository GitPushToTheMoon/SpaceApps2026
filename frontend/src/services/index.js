import { ApiDataService, MockDataService } from './DataService';
import { AgentService, MockAgentService } from './AgentService';

// The real backend is used by default. To work without it, set in frontend/.env:
//   VITE_USE_MOCK_DATA=true    (item library from data/mockData.js)
//   VITE_USE_MOCK_AGENT=true   (no assessments; status shows "Backend unreachable")
const useMockData = import.meta.env.VITE_USE_MOCK_DATA === 'true';
const useMockAgent = import.meta.env.VITE_USE_MOCK_AGENT === 'true';

export const dataService = useMockData ? new MockDataService() : new ApiDataService();
export const agentService = useMockAgent ? new MockAgentService() : new AgentService();
