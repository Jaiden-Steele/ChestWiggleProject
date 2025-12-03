import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ============================================
# CONFIG: PITT COLOR PALETTE + TEXT SIZE
# ============================================
PITT_BLUE = "#003594"
PITT_GOLD = "#FFB81C"
BLOCK_FACE = "#E9F0FA"    # very light Pitt blue
TEXT_SIZE = 15
BLOCK_WIDTH = 3.0
BLOCK_HEIGHT = 1.5
ARROW_SCALE = 22  # arrowhead size


# ============================================
# Helper: Draw a block
# ============================================
def add_block(ax, cx, cy, text):
    x = cx - BLOCK_WIDTH/2
    y = cy - BLOCK_HEIGHT/2
    box = FancyBboxPatch(
        (x, y), BLOCK_WIDTH, BLOCK_HEIGHT,
        boxstyle="round,pad=0.25,rounding_size=0.18",
        linewidth=2.5,
        edgecolor=PITT_BLUE,
        facecolor=BLOCK_FACE
    )
    ax.add_patch(box)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=TEXT_SIZE, color=PITT_BLUE)


# ============================================
# Helper: Draw a small clean arrow between blocks
# ============================================
def draw_arrow(ax, start_x, end_x, y):
    ax.annotate(
        "",
        xy=(end_x, y),
        xytext=(start_x, y),
        arrowprops=dict(
            arrowstyle="-|>",
            lw=2.8,
            color=PITT_BLUE,
            shrinkA=6,
            shrinkB=6,
            mutation_scale=ARROW_SCALE
        )
    )


# ============================================
# FIGURE 1: SYSTEM FLOW (Signal Processing Pipeline)
# ============================================
def make_system_flow():
    fig, ax = plt.subplots(figsize=(18, 4))
    ax.axis("off")

    xs = [2, 6, 10, 14, 18]
    y = 2

    labels = [
        "Raw Sensor Data\n(ax, ay, az)",
        "Preprocessing\n(DC Removal)",
        "Bandpass Filter\n5–15 Hz",
        "Feature Extraction\nFreq / Amp / SNR",
        "Clinical State Output\nNormal • Low • Fault"
    ]

    # Draw blocks
    for x, text in zip(xs, labels):
        add_block(ax, x, y, text)

    # Draw arrows
    for i in range(len(xs) - 1):
        draw_arrow(ax, xs[i] + BLOCK_WIDTH/2 + 0.3,
                        xs[i+1] - BLOCK_WIDTH/2 - 0.3, y)

    ax.set_xlim(0, 20)
    ax.set_ylim(0, 4)
    plt.tight_layout()
    plt.savefig("SYSTEM_FLOW_PITT.png", dpi=300)
    plt.close()


# ============================================
# FIGURE 2: BLOCK DIAGRAM (System Architecture)
# ============================================
def make_block_diagram():
    fig, ax = plt.subplots(figsize=(18, 4.5))
    ax.axis("off")

    xs = [2, 6, 10, 14, 18]
    y = 2

    labels = [
        "MPU6050 Sensor",
        "Arduino\nData Acquisition",
        "USB Serial Stream\n(ax, ay, az)",
        "Python HFOV Processor\nFiltering + Metrics",
        "Live UI\nWaveforms • Alerts"
    ]

    # Draw blocks
    for x, text in zip(xs, labels):
        add_block(ax, x, y, text)

    # Draw arrows
    for i in range(len(xs) - 1):
        draw_arrow(ax, xs[i] + BLOCK_WIDTH/2 + 0.3,
                        xs[i+1] - BLOCK_WIDTH/2 - 0.3, y)

    ax.set_xlim(0, 20)
    ax.set_ylim(0, 4)
    plt.tight_layout()
    plt.savefig("BLOCK_DIAGRAM_PITT.png", dpi=300)
    plt.close()


# ============================================
# RUN BOTH DIAGRAMS
# ============================================
if __name__ == "__main__":
    make_system_flow()
    make_block_diagram()
    print("\nGenerated poster-ready diagrams:")
    print("  • SYSTEM_FLOW_PITT.png")
    print("  • BLOCK_DIAGRAM_PITT.png\n")
