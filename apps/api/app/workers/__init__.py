"""
GPU Worker interface layer.

Each worker module implements the interface for a pipeline stage.
Mock implementations are used for local dev; real implementations
will call ComfyUI API on RunPod/EC2 GPU instances.
"""
