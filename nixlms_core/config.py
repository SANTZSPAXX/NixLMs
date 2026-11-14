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
    lif_output_learning_rate: float = 0.025
    lif_retrieval_threshold: float = 0.45
    decoder_hidden_size: int = 16
    decoder_embedding_size: int = 16
    decoder_max_vocab: int = 512
    decoder_learning_rate: float = 0.03
    decoder_max_sequence_length: int = 32
    decoder_min_confidence: float = 0.15
    decoder_max_tokens: int = 40
