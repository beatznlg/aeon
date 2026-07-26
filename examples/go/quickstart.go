package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/beatznlg/aeon/sdk/go/aeon"
)

func main() {
	// Get the API URL from the environment or use the default
	apiURL := os.Getenv("AEON_PYTHON_URL")
	if apiURL == "" {
		apiURL = "http://localhost:5000"
	}

	// Get the API key from the environment (optional)
	apiKey := os.Getenv("AEON_API_KEY")

	// Create the client
	var client *aeon.Client
	if apiKey != "" {
		client = aeon.NewClient(apiURL, aeon.WithAPIKey(apiKey), aeon.WithTimeout(60*time.Second))
	} else {
		client = aeon.NewClient(apiURL)
	}

	fmt.Printf("🔌 Connecting to AEON OS at %s\n\n", apiURL)

	// ── 1. Health Check ──
	fmt.Println("═══ Health Check ═══")
	health, err := client.Health()
	if err != nil {
		log.Fatalf("Health check failed: %v", err)
	}
	fmt.Printf("Status: %v\n", health["status"])
	fmt.Println()

	// ── 2. Login (or skip if API key is set) ──
	if apiKey == "" {
		fmt.Println("═══ Auth - Login ═══")
		email := os.Getenv("AEON_ADMIN_EMAIL")
		password := os.Getenv("AEON_ADMIN_PASSWORD")
		if email == "" || password == "" {
			log.Fatal("Set AEON_ADMIN_EMAIL and AEON_ADMIN_PASSWORD env vars (or AEON_API_KEY)")
		}
		loginResp, err := client.Login(email, password)
		if err != nil {
			log.Fatalf("Login failed: %v", err)
		}
		fmt.Printf("Logged in as: %v\n", loginResp["user"])
		fmt.Println()
	}

	// ── 3. Chat ──
	fmt.Println("═══ Chat ═══")
	reply, err := client.Chat("What is AEON OS?", "", "")
	if err != nil {
		log.Printf("Chat error: %v\n", err)
	} else {
		if response, ok := reply["response"]; ok {
			fmt.Printf("AEON: %v\n", response)
		} else if msg, ok := reply["message"]; ok {
			fmt.Printf("AEON: %v\n", msg)
		}
	}
	fmt.Println()

	// ── 4. List Workspaces ──
	fmt.Println("═══ Workspaces ═══")
	workspaces, err := client.ListWorkspaces()
	if err != nil {
		log.Printf("List workspaces error: %v\n", err)
	} else {
		fmt.Printf("Workspaces: %v\n", workspaces)
	}
	fmt.Println()

	// ── 5. LLM Providers ──
	fmt.Println("═══ LLM Providers ═══")
	providers, err := client.ListLLMProviders()
	if err != nil {
		log.Printf("List providers error: %v\n", err)
	} else {
		fmt.Printf("Available providers: %v\n", providers)
	}
	fmt.Println()

	fmt.Println("✅ Done! See examples/go/quickstart.go and docs/ for more.")
}
