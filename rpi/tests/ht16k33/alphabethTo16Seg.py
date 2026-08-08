# segment_real_gui.py
import tkinter as tk

selected = set()
segments = {}  # jetzt: name -> LISTE von polys

def toggle(seg):
    if seg in selected:
        selected.remove(seg)
        for poly in segments[seg]:
            canvas.itemconfig(poly, fill="gray8")
    else:
        selected.add(seg)
        for poly in segments[seg]:
            canvas.itemconfig(poly, fill="lime")

    update_output()

def segments_to_hex():
    value = 0
    for seg in selected:
        bit = int(seg[2:])
        value |= 1 << bit
    return value

def update_output():
    val = segments_to_hex()
    hex_label.config(text=f"HEX: 0x{val:04X}")
    bin_label.config(text=f"BIN: {val:016b}")

def create_segment(name, coords):
    poly = canvas.create_polygon(coords, fill="gray20", outline="white", width=2)
    canvas.tag_bind(poly, "<Button-1>", lambda e, n=name: toggle(n))

    # 🔥 WICHTIG: mehrere Segmente pro Row speichern
    if name not in segments:
        segments[name] = []
    segments[name].append(poly)

    # Mittelpunkt berechnen
    xs = coords[0::2]
    ys = coords[1::2]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    canvas.create_text(cx, cy, text=name, fill="white", font=("Arial", 9))

# GUI Setup
root = tk.Tk()
root.title("16-Segment Editor (Real Layout)")

canvas = tk.Canvas(root, width=320, height=520, bg="black")
canvas.pack()

# ----------------------------
# Segment Layout (16-Segment)
# ----------------------------

create_segment("RW5",  [30,50, 150,50, 130,80, 60,80])
create_segment("RW5",  [150,50, 270,50, 240,80, 170,80])

create_segment("RW7",  [30,50, 60,80, 60,265, 30,280])
create_segment("RW1",  [270,50, 240,80, 240,265, 270,280])

create_segment("RW4",  [135,80, 165,80, 165,270, 135,270])

create_segment("RW6",  [60,95, 85,80, 165,270, 135,270])
create_segment("RW3",  [240,95, 220,80, 135,270,165,270])

create_segment("RW8",  [60,270, 130,270, 130,300, 60,300])
create_segment("RW0",  [170,270, 240,270, 240,300, 170,300])

create_segment("RW9",  [30,285, 60,300, 60,470, 30,500])
create_segment("RW15", [240,300, 270,285, 270,500, 240,470])

create_segment("RW12", [135,300, 165,300, 165,470, 135,470])

create_segment("RW11", [165,315, 135,300, 60,455,85,470])
create_segment("RW14", [135,300, 165,300, 240,455,215,470])

create_segment("RW10", [30,500, 145,500, 130,470, 60,470])
create_segment("RW13", [155,500, 270,500, 240,470, 170,470])

create_segment("RW2",  [280,470, 310,470, 310,500, 280,500])

# Labels
hex_label = tk.Label(root, text="HEX: 0x0000", font=("Courier", 10))
hex_label.pack()

bin_label = tk.Label(root, text="BIN: 0000000000000000", font=("Courier", 7))
bin_label.pack()

root.mainloop()
