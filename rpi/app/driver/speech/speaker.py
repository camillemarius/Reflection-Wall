import os
import subprocess
import tempfile

class SpeechAssistant:
    def __init__(self):
        self.device = "plughw:2,0"
        
        base_dir = os.path.dirname(__file__)
        self.model_path = os.path.join(
            base_dir,
            "voices/de_DE-thorsten-high.onnx"
            #"voices/en_US-amy-medium.onnx"
        )

    def speak(self, text):
        if not text.strip():
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        cmd = [
            "piper",
            "--model", self.model_path,
            "--output_file", wav_path,
        ]

        subprocess.run(cmd, input=text, text=True)

        subprocess.run(["aplay", "-D", self.device, wav_path])

        os.remove(wav_path)