// Package aeon provides a Go client for the AEON OS API.
//
// Usage:
//
//    import "github.com/beatznlg/aeon/sdk/go/aeon"
//
//    client := aeon.NewClient("https://your-backend.com", aeon.WithAPIKey("aeon_..."))
//
//    health, err := client.Health()
//    reply, err := client.Chat("Hello!")
//
package aeon

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
)

// Error represents an AEON API error.
type Error struct {
	Message    string
	StatusCode int
	Response   interface{}
}

func (e *Error) Error() string {
	if e.StatusCode > 0 {
		return fmt.Sprintf("AeonError %d: %s", e.StatusCode, e.Message)
	}
	return fmt.Sprintf("AeonError: %s", e.Message)
}

// ClientOption configures an AeonClient.
type ClientOption func(*Client)

// WithAPIKey sets the API key for authentication.
func WithAPIKey(key string) ClientOption {
	return func(c *Client) { c.apiKey = key }
}

// WithToken sets the JWT token for authentication.
func WithToken(token string) ClientOption {
	return func(c *Client) { c.token = token }
}

// WithTimeout sets the default request timeout.
func WithTimeout(timeout time.Duration) ClientOption {
	return func(c *Client) { c.timeout = timeout }
}

// WithHTTPClient sets a custom *http.Client.
func WithHTTPClient(hc *http.Client) ClientOption {
	return func(c *Client) { c.http = hc }
}

// Client is the AEON OS API client.
type Client struct {
	baseURL string
	apiKey  string
	token   string
	timeout time.Duration
	http    *http.Client
}

// NewClient creates a new AEON API client.
func NewClient(baseURL string, opts ...ClientOption) *Client {
	if baseURL == "" {
		baseURL = os.Getenv("AEON_PYTHON_URL")
		if baseURL == "" {
			baseURL = "http://localhost:5000"
		}
	}
	c := &Client{
		baseURL: baseURL,
		timeout: 120 * time.Second,
		http:    &http.Client{Timeout: 120 * time.Second},
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

func (c *Client) request(method, path string, query map[string]string, body interface{}) (map[string]interface{}, error) {
	u, err := url.Parse(c.baseURL + path)
	if err != nil {
		return nil, fmt.Errorf("aeon: invalid url: %w", err)
	}
	for k, v := range query {
		q := u.Query()
		q.Set(k, v)
		u.RawQuery = q.Encode()
	}
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("aeon: marshal body: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, u.String(), reqBody)
	if err != nil {
		return nil, fmt.Errorf("aeon: create request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("aeon: request failed: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("aeon: read response: %w", err)
	}

	var data map[string]interface{}
	if len(bodyBytes) > 0 {
		if err := json.Unmarshal(bodyBytes, &data); err != nil {
			return nil, fmt.Errorf("aeon: decode response: %w", err)
		}
	}

	if resp.StatusCode >= 400 {
		errMsg, _ := data["error"].(string)
		if errMsg == "" {
			errMsg = resp.Status
		}
		return nil, &Error{Message: errMsg, StatusCode: resp.StatusCode, Response: data}
	}
	return data, nil
}

func (c *Client) get(path string, query map[string]string) (map[string]interface{}, error) {
	return c.request(http.MethodGet, path, query, nil)
}

func (c *Client) post(path string, body interface{}) (map[string]interface{}, error) {
	return c.request(http.MethodPost, path, nil, body)
}

func (c *Client) patch(path string, body interface{}) (map[string]interface{}, error) {
	return c.request(http.MethodPatch, path, nil, body)
}

func (c *Client) del(path string) (map[string]interface{}, error) {
	return c.request(http.MethodDelete, path, nil, nil)
}

// ── Health ───────────────────────────────────────────────────────────────

func (c *Client) Health() (map[string]interface{}, error) {
	return c.get("/health", nil)
}

func (c *Client) Liveness() (map[string]interface{}, error) {
	return c.get("/live", nil)
}

func (c *Client) Readiness() (map[string]interface{}, error) {
	return c.get("/ready", nil)
}

func (c *Client) DetailedHealth() (map[string]interface{}, error) {
	return c.get("/health/detailed", nil)
}

// ── Auth ─────────────────────────────────────────────────────────────────

func (c *Client) Login(email, password string) (map[string]interface{}, error) {
	data, err := c.post("/auth/login", map[string]interface{}{
		"email": email, "password": password,
	})
	if err == nil {
		if token, ok := data["token"].(string); ok {
			c.token = token
		}
	}
	return data, err
}

func (c *Client) Register(email, password, name string) (map[string]interface{}, error) {
	return c.post("/auth/register", map[string]interface{}{
		"email": email, "password": password, "name": name,
	})
}

func (c *Client) Me() (map[string]interface{}, error) {
	return c.get("/auth/me", nil)
}

// ── Workspaces & Chat ────────────────────────────────────────────────────

func (c *Client) ListWorkspaces() (map[string]interface{}, error) {
	return c.get("/workspaces", nil)
}

func (c *Client) Chat(query, workspaceID, provider string) (map[string]interface{}, error) {
	body := map[string]interface{}{"query": query}
	if provider != "" {
		body["provider"] = provider
	}
	if workspaceID != "" {
		return c.post("/workspaces/"+workspaceID+"/chat", body)
	}
	return c.post("/chat", body)
}

func (c *Client) WorkspaceHistory(workspaceID string, limit int) (map[string]interface{}, error) {
	return c.get("/workspaces/"+workspaceID+"/history", map[string]string{
		"limit": fmt.Sprintf("%d", limit),
	})
}

// ── Apps ─────────────────────────────────────────────────────────────────

func (c *Client) AppTick(appID, query string) (map[string]interface{}, error) {
	return c.post("/apps/"+appID+"/tick", map[string]interface{}{"query": query})
}

func (c *Client) AppChat(appID, query string) (map[string]interface{}, error) {
	return c.post("/apps/"+appID+"/chat", map[string]interface{}{"query": query})
}

// ── Workflows ────────────────────────────────────────────────────────────

func (c *Client) ListWorkflows() (map[string]interface{}, error) {
	return c.get("/workflows", nil)
}

func (c *Client) CreateWorkflow(name string, nodes, edges []interface{}) (map[string]interface{}, error) {
	return c.post("/workflows", map[string]interface{}{
		"name": name, "nodes": nodes, "edges": edges,
	})
}

func (c *Client) GetWorkflow(workflowID string) (map[string]interface{}, error) {
	return c.get("/workflows/"+workflowID, nil)
}

func (c *Client) DeleteWorkflow(workflowID string) (map[string]interface{}, error) {
	return c.del("/workflows/" + workflowID)
}

func (c *Client) RunWorkflow(workflowID string, inputs map[string]interface{}) (map[string]interface{}, error) {
	return c.post("/workflows/"+workflowID+"/run", map[string]interface{}{
		"inputs": inputs,
	})
}

// ── Swarm ────────────────────────────────────────────────────────────────

func (c *Client) RunSwarm(appIDs []string, prompt string, roles map[string]string) (map[string]interface{}, error) {
	return c.post("/swarm/run", map[string]interface{}{
		"app_ids": appIDs, "prompt": prompt, "roles": roles,
	})
}

func (c *Client) SwarmStatus(swarmID string) (map[string]interface{}, error) {
	return c.get("/swarm/"+swarmID, nil)
}

func (c *Client) SwarmMessages(swarmID string) (map[string]interface{}, error) {
	return c.get("/swarm/"+swarmID+"/messages", nil)
}

// ── API Keys ─────────────────────────────────────────────────────────────

func (c *Client) ListAPIKeys(workspaceID string) (map[string]interface{}, error) {
	if workspaceID != "" {
		return c.get("/api-keys", map[string]string{"workspace_id": workspaceID})
	}
	return c.get("/api-keys", nil)
}

func (c *Client) CreateAPIKey(name, workspaceID, role string) (map[string]interface{}, error) {
	return c.post("/api-keys", map[string]interface{}{
		"name": name, "workspace_id": workspaceID, "role": role,
	})
}

func (c *Client) GetAPIKey(keyID string) (map[string]interface{}, error) {
	return c.get("/api-keys/"+keyID, nil)
}

func (c *Client) UpdateAPIKey(keyID, name, role string, active *bool) (map[string]interface{}, error) {
	body := map[string]interface{}{}
	if name != "" {
		body["name"] = name
	}
	if role != "" {
		body["role"] = role
	}
	if active != nil {
		body["active"] = *active
	}
	return c.patch("/api-keys/"+keyID, body)
}

func (c *Client) DeleteAPIKey(keyID string) (map[string]interface{}, error) {
	return c.del("/api-keys/" + keyID)
}

// ── Integrations ─────────────────────────────────────────────────────────

func (c *Client) ListIntegrations() (map[string]interface{}, error) {
	return c.get("/integrations", nil)
}

func (c *Client) CreateIntegration(type_, name string, config map[string]interface{}) (map[string]interface{}, error) {
	return c.post("/integrations", map[string]interface{}{
		"type": type_, "name": name, "config": config,
	})
}

func (c *Client) RunIntegration(integrationID, endpoint, method string, payload interface{}) (map[string]interface{}, error) {
	return c.post("/integrations/"+integrationID+"/run", map[string]interface{}{
		"endpoint": endpoint, "method": method, "payload": payload,
	})
}

func (c *Client) GetIntegrationCatalog() (map[string]interface{}, error) {
	return c.get("/integrations/catalog", nil)
}

// ── Billing & Usage ──────────────────────────────────────────────────────

func (c *Client) GetBillingStatus(workspaceID string) (map[string]interface{}, error) {
	return c.get("/billing/"+workspaceID, nil)
}

func (c *Client) RecordUsage(events []interface{}) (map[string]interface{}, error) {
	return c.post("/usage", events)
}

// ── LLM ──────────────────────────────────────────────────────────────────

func (c *Client) ListLLMProviders() (map[string]interface{}, error) {
	return c.get("/llm/providers", nil)
}

func (c *Client) SwitchLLMProvider(provider string) (map[string]interface{}, error) {
	return c.post("/llm/switch", map[string]interface{}{"provider": provider})
}

func (c *Client) TestLLMProvider(provider string) (map[string]interface{}, error) {
	return c.post("/llm/test", map[string]interface{}{"provider": provider})
}

// ── RAG / Knowledge Bases ───────────────────────────────────────────────

func (c *Client) ListKnowledgeBases() (map[string]interface{}, error) {
	return c.get("/knowledge-bases", nil)
}

func (c *Client) CreateKnowledgeBase(name, description string) (map[string]interface{}, error) {
	return c.post("/knowledge-bases", map[string]interface{}{
		"name": name, "description": description,
	})
}

func (c *Client) QueryKnowledgeBase(kbID, query string, topK int) (map[string]interface{}, error) {
	return c.post("/knowledge-bases/"+kbID+"/query", map[string]interface{}{
		"query": query, "top_k": topK,
	})
}

// ── Governance ───────────────────────────────────────────────────────────

func (c *Client) ListGovernanceAudit() (map[string]interface{}, error) {
	return c.get("/governance/audit", nil)
}

func (c *Client) ListGovernanceCompliance() (map[string]interface{}, error) {
	return c.get("/governance/compliance", nil)
}

func (c *Client) GetGovernanceRetention() (map[string]interface{}, error) {
	return c.get("/governance/retention", nil)
}
