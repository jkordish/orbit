package main

import "testing"

func TestGreet(t *testing.T) {
	if got := greet("Mac"); got != "Hello, Mac!" {
		t.Fatalf("unexpected greeting: %q", got)
	}
}
