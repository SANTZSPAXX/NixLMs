import hashlib, math
from .utils import tokenize

class HashEncoder:
    """Codificação lexical determinística por hashing; não é embedding semântico pré-treinado."""
    def __init__(self, dimensions=64): self.dimensions=dimensions
    def encode(self, text):
        vec=[0.0]*self.dimensions
        for pos,word in enumerate(tokenize(text)):
            digest=hashlib.blake2b(word.encode(),digest_size=16).digest()
            idx=int.from_bytes(digest[:4],"little")%self.dimensions
            sign=1.0 if digest[4]%2 else -1.0
            vec[idx]+=sign/(1+0.08*pos)
        norm=math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x/norm for x in vec]
