// Package controls provides an in-memory control registry.
package controls

import (
	"sort"
	"sync"
)

type Control struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Owner   string `json:"owner"`
	Enabled bool   `json:"enabled"`
}

type Registry struct {
	mu       sync.RWMutex
	controls map[string]Control
}

func NewRegistry() *Registry {
	return &Registry{
		controls: map[string]Control{
			"market-hours": {
				ID:      "market-hours",
				Name:    "Market hours",
				Owner:   "operations",
				Enabled: true,
			},
			"risk-threshold": {
				ID:      "risk-threshold",
				Name:    "Risk threshold",
				Owner:   "risk",
				Enabled: true,
			},
			"trade-limits": {
				ID:      "trade-limits",
				Name:    "Trade limits",
				Owner:   "compliance",
				Enabled: true,
			},
		},
	}
}

func (r *Registry) List() []Control {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := make([]string, 0, len(r.controls))
	for id := range r.controls {
		ids = append(ids, id)
	}
	sort.Strings(ids)

	controls := make([]Control, 0, len(ids))
	for _, id := range ids {
		controls = append(controls, r.controls[id])
	}
	return controls
}

func (r *Registry) Get(id string) (Control, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	control, ok := r.controls[id]
	return control, ok
}

func (r *Registry) Toggle(id string) (Control, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()

	control, ok := r.controls[id]
	if !ok {
		return Control{}, false
	}
	control.Enabled = !control.Enabled
	r.controls[id] = control
	return control, true
}
