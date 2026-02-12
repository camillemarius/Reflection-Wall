# core/segment_chain.py
from .segment_module import SegmentModule

class SegmentChain:
    def __init__(self, modules):
        self.modules = modules
        self.chars_per_chain = sum(m.chars_per_module for m in modules)

    def clear(self):
        for module in self.modules:
            module.clear()

    def set_text(self, text):
        """
        Teilt den Text auf die Module auf und setzt ihn
        """
        start = 0
        for module in self.modules:
            end = start + module.chars_per_module
            chunk = text[start:end]
            module.set_text(chunk)
            start = end
