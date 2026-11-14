from dataclasses import dataclass

@dataclass
class CoreConfig:
    input_size: int = 64
    hidden_size: int = 48
    output_size: int = 32
    steps: int = 24
    threshold: float = 0.08
    leak: float = 0.88
    learning_rate: float = 0.025
    seed: int = 42
    max_memory_items: int = 2000
    confidence_threshold: float = 0.12
