"""
MAIA Race Guard Tests — DFlash/Sentinel Race Condition Scenarios
================================================================
Tests the BlockSynchronizer against real-world race conditions:
1. Sequential emission without decision yet (blocks hold in buffer)
2. Decision arrives out of order (stale decision dropped)
3. Sentinel timeout (rollback triggered)
4. Multiple blocks in flight simultaneously
5. Rapid emission before decisions (buffer growth)
6. Rollback to safe checkpoint
7. Governed block context manager lifecycle
"""
