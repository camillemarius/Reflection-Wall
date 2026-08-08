"""
fram_text_storage.py

Kompatibel zu ESP FramTextStorage

Format:
ADDR 0:
[LEN HIGH][LEN LOW][TEXT]
"""

from fram import FRAM


class FramTextStorage:

    TEXT_ADDRESS = 0
    MAX_TEXT_LENGTH = 1024


    def __init__(self, fram=None):
        self.fram = fram or FRAM()


    def begin(self):
        try:
            self.fram.read(
                self.TEXT_ADDRESS,
                1
            )
            return True
        except:
            return False


    def write_text(self, text):

        data = text.encode(
            "utf-8"
        )

        length = len(data)

        if length > self.MAX_TEXT_LENGTH:
            return False


        self.fram.write(
            self.TEXT_ADDRESS,
            bytes([
                (length >> 8) & 0xFF,
                length & 0xFF
            ])
        )


        self.fram.write(
            self.TEXT_ADDRESS + 2,
            data
        )

        return True



    def read_text(self):

        length_data = self.fram.read(
            self.TEXT_ADDRESS,
            2
        )

        length = (
            (length_data[0] << 8)
            |
            length_data[1]
        )


        if length == 0 or length > self.MAX_TEXT_LENGTH:
            return ""


        data = self.fram.read(
            self.TEXT_ADDRESS + 2,
            length
        )

        return data.decode(
            "utf-8",
            errors="ignore"
        )



    def clear(self):

        self.fram.write(
            self.TEXT_ADDRESS,
            bytes([0, 0])
        )



    def close(self):
        self.fram.close()