"""
MAIA Neural Tool Dispatcher
========================
The "CPU Scheduler" of the MAIA-Enterprise OS.
Bridges probabilistic reasoning (thinking) to deterministic action (JSON-RPC).

Implements Interrupt-and-Reconfigure pattern:
1. Detects tool intent in <|think|> stream
2. Hot-swaps neural weights via LoRAX
3. Applies Logit Bias firewall
4. Generates governed parameters
5. Dispatches via JSON-RPC
6. Logs to forensics for SR 26-02 compliance
"""
