"""
MAIA Gemma4 Thinking Airlock
=============================
Real-time reasoning interceptor for Gemma 4.

Intercepts the <|think|> channel to audit reasoning BEFORE
action is taken. Implements stateful parsing for Gemma 4's
thinking tokens.

SR 26-02: "Effective Challenge" - audits intent before action.
"""
