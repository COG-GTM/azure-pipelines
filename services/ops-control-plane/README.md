Runnable Go scaffold for the ops-control-plane migration demo.
Mirrors services/pricing-engine with a minimal build, test, and HTTP server path.
Needs Go 1.22+. Run `go run ./cmd/server` and check http://localhost:8080/healthz or `/v1/controls` (set `PORT` to change the port).
