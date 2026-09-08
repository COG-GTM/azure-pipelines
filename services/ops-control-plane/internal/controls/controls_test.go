package controls

import "testing"

func TestRegistryOperations(t *testing.T) {
	tests := []struct {
		name string
		run  func(*testing.T, *Registry)
	}{
		{
			name: "list returns seeded controls",
			run: func(t *testing.T, registry *Registry) {
				if got := registry.List(); len(got) != 3 {
					t.Fatalf("List() returned %d controls, want 3", len(got))
				}
			},
		},
		{
			name: "get returns existing control",
			run: func(t *testing.T, registry *Registry) {
				got, ok := registry.Get("trade-limits")
				if !ok {
					t.Fatal("Get() reported an existing control as missing")
				}
				if got.Name != "Trade limits" || got.Owner != "compliance" {
					t.Fatalf("Get() returned %+v", got)
				}
			},
		},
		{
			name: "get returns unknown id",
			run: func(t *testing.T, registry *Registry) {
				if _, ok := registry.Get("unknown"); ok {
					t.Fatal("Get() found an unknown control")
				}
			},
		},
		{
			name: "toggle changes enabled state",
			run: func(t *testing.T, registry *Registry) {
				got, ok := registry.Toggle("trade-limits")
				if !ok {
					t.Fatal("Toggle() reported an existing control as missing")
				}
				if got.Enabled {
					t.Fatal("Toggle() left the control enabled")
				}
			},
		},
		{
			name: "toggle returns unknown id",
			run: func(t *testing.T, registry *Registry) {
				if _, ok := registry.Toggle("unknown"); ok {
					t.Fatal("Toggle() found an unknown control")
				}
			},
		},
		{
			name: "list returns independent values",
			run: func(t *testing.T, registry *Registry) {
				got := registry.List()
				got[0].Enabled = !got[0].Enabled
				again, ok := registry.Get(got[0].ID)
				if !ok || again.Enabled == got[0].Enabled {
					t.Fatal("List() exposed mutable registry state")
				}
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			test.run(t, NewRegistry())
		})
	}
}
