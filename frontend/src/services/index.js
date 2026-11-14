import { ApiDataService, MockDataService } from './DataService';
import { AgentService, MockAgentService } from './AgentService';

// Flip these in frontend/.env when the backend is ready:
//   VITE_USE_MOCK_DATA=false
//   VITE_USE_MOCK_AGENT=false
const useMockData = import.meta.env.VITE_USE_MOCK_DATA !== 'false';
const useMockAgent = import.meta.env.VITE_USE_MOCK_AGENT !== 'false';

export const dataService = useMockData ? new MockDataService() : new ApiDataService('/api');
export const agentService = useMockAgent ? new MockAgentService() : new AgentService({ endpoint: '/api/agent/complete' });
