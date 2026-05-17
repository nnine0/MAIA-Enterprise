"""
MAIA Thinking Airlock - Layer 8 Reasoning Interceptor
=====================================================

With Gemma 4, MAIA doesn't just check the output; it checks the thought process.
This prevents "Deceptive Alignment" (where a model plans a violation in its head
but hides it in the final answer).

The Thinking Airlock scans <|channel>thought blocks before the model moves to [Final Answer].
"""
