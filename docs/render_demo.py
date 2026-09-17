"""Render demo PNGs and check the reviewed release assets."""

import argparse
import subprocess
import textwrap
from hashlib import file_digest
from pathlib import Path

import imageio_ffmpeg  # type: ignore[import-untyped]
from demo.run_demo import DemoResult, compute_constructed_result, compute_result, serialize_result
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
VIDEO_SIZE = (1800, 1080)
VIDEO_SECONDS = 90
VIDEO_FPS = 24
GIF_SECONDS = 20
GIF_FPS = 10
TRANSITION_LABELS = {
    "reaches": "Reach endpoint",
    "exploits": "Exploit",
    "reads": "Read credentials",
    "authenticates_as": "Authenticate to cloud",
}
# Pin the reviewed pair without relying on platform-specific GIF encoding.
REVIEWED_RECORDINGS = {
    "demo.mp4": "4429e0bb2c872027ab43e25d64008f8b6f5d793e347bf68e11713b2c71156b5c",
    "demo.gif": "827e7716c4e039358fd27f4500ea6c91d86d820e7d421fb2c52dba36008b9192",
}


def draw_text(
    image: Image.Image,
    position: tuple[int, int],
    text: str,
    *,
    size: int = 24,
    columns: int = 100,
    color: str,
) -> None:
    wrapped = "\n".join(
        "\n".join(textwrap.wrap(line, columns, break_long_words=False, break_on_hyphens=False))
        for line in text.split("\n")
    )
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=size)
    bounds = draw.multiline_textbbox(position, wrapped, font=font, spacing=8)
    if bounds[2] > image.width - 24 or bounds[3] > image.height - 24:
        raise ValueError(f"Media text exceeds the canvas: {text[:80]}")
    draw.multiline_text(position, wrapped, font=font, fill=color, spacing=8)


def draw_graph_link(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    is_removed: bool,
) -> None:
    # A smooth curve with horizontal tangents at both ends.
    points = []
    for step in range(81):
        t = step / 80
        points.append(
            (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * (3 * t**2 - 2 * t**3),
            )
        )
    for step in range(0, 80, 8):
        if not (is_removed and 24 <= step < 56):
            draw.line(points[step : step + 5], fill=color, width=4)
    if is_removed:
        x, y = points[40]
        draw.line((x - 12, y - 12, x + 12, y + 12), fill=color, width=5)
        draw.line((x - 12, y + 12, x + 12, y - 12), fill=color, width=5)
    else:
        x, y = end
        draw.polygon(((x - 12, y - 7), (x, y), (x - 12, y + 7)), fill=color)


def render_graph(result: DemoResult, is_severed: bool) -> Image.Image:
    (path,) = result.paths.paths
    (selected,) = result.ranked_interventions
    nodes = {node.id: node for node in result.graph.nodes}
    edges = {edge.id: edge for edge in result.graph.edges}
    removed_ids = set(result.removed_transition_ids) if is_severed else set()
    coordinates = ((180, 450), (540, 490), (900, 430), (1260, 480), (1620, 440), (1980, 475))
    positions = dict(zip(path.node_ids, coordinates, strict=True))
    image = Image.new("RGB", (2160, 960), "#181818")
    draw = ImageDraw.Draw(image)
    red, white, gray = "#ED2336", "#E5E5E5", "#9B9B9B"
    route_color = gray if is_severed else red
    title = (
        f"Fortune 600 / After modeled application of {selected.intervention.id}"
        if is_severed
        else "Fortune 600 / Constructed attack graph"
    )
    draw_text(image, (64, 56), title, size=40, color=white)
    draw_text(image, (64, 118), "Armadin / Kill Chains and Coffee / Episode 4", size=26, color=gray)

    for edge_id in path.edge_ids:
        edge = edges[edge_id]
        start_x, start_y = positions[edge.source]
        end_x, end_y = positions[edge.target]
        is_removed = edge_id in removed_ids
        color = red if is_removed else route_color
        draw_graph_link(draw, (start_x + 30, start_y), (end_x - 30, end_y), color, is_removed)
        label = (
            nodes[edge.enabled_by].label if edge.enabled_by else TRANSITION_LABELS[edge.type.value]
        )
        if is_removed:
            label += f"\nREMOVED by {selected.intervention.id}"
        draw_text(
            image,
            ((start_x + end_x) // 2 - 144, 606),
            label,
            size=26,
            columns=24,
            color=color,
        )

    for index, node_id in enumerate(path.node_ids):
        node = nodes[node_id]
        x, y = positions[node_id]
        draw_text(
            image,
            (x - 144, 222),
            f"{index + 1}. {node.label}",
            size=30,
            columns=22,
            color=white,
        )
        draw.line((x, 374, x, y - 32), fill="#555555", width=2)
        if node.type.value == "entry_point":
            draw.ellipse((x - 24, y - 24, x + 24, y + 24), outline=route_color, width=3)
            draw.ellipse((x - 10, y - 24, x + 10, y + 24), outline=route_color, width=2)
            draw.line((x - 24, y, x + 24, y), fill=route_color, width=2)
        elif node.type.value == "objective":
            draw.polygon(
                (
                    (x - 26, y - 26),
                    (x + 26, y - 26),
                    (x + 22, y + 12),
                    (x, y + 30),
                    (x - 22, y + 12),
                ),
                outline=route_color,
                width=3,
            )
        else:
            draw.polygon(
                (
                    (x - 27, y - 18),
                    (x + 15, y - 18),
                    (x + 27, y - 6),
                    (x + 27, y + 18),
                    (x - 27, y + 18),
                ),
                fill=route_color,
            )

    draw.line((64, 784, 2096, 784), fill="#444444", width=2)
    if is_severed:
        draw_text(
            image,
            (64, 810),
            f"{selected.intervention.id}: {selected.intervention.name}",
            size=32,
            color=white,
        )
        draw_text(
            image,
            (64, 862),
            f"{len(result.solution.covered_path_ids)}/{len(result.paths.paths)} "
            f"supplied validated paths severed / Cost: {selected.cost_units:g} assumed "
            f"implementation unit / {result.solution.guarantee.value.upper()} minimum cost",
            size=26,
            color=white,
        )
    else:
        draw_text(
            image,
            (64, 810),
            f"Supplied source-validated paths: {len(result.paths.paths)}",
            size=32,
            color=white,
        )
    draw_text(
        image,
        (64, 900),
        "Gray: retained transitions. Red X: modeled removal."
        if is_severed
        else "Red: source-validated route.",
        size=20,
        color=gray,
    )
    return image


def verify_media(result: DemoResult, directory: Path) -> None:
    for name, expected in (
        ("fortune600-before.png", render_graph(result, False)),
        ("fortune600-after.png", render_graph(result, True)),
    ):
        with Image.open(directory / name) as image:
            if image.format != "PNG" or image.size != expected.size:
                raise ValueError(f"{name}: expected a full-size PNG release image.")
            if ImageChops.difference(image.convert("RGB"), expected).getbbox():
                raise ValueError(f"{name} differs from the current computed result.")

    for name, expected_hash in REVIEWED_RECORDINGS.items():
        with (directory / name).open("rb") as recording:
            actual_hash = file_digest(recording, "sha256").hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(
                f"{name} differs from the reviewed recording. "
                "Review replacement media before updating its expected hash."
            )

    decoded = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(directory / "demo.mp4"),
            "-map",
            "0:v:0",
            "-progress",
            "pipe:1",
            "-nostats",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    progress = dict(line.split("=", 1) for line in decoded.stdout.splitlines() if "=" in line)
    if (
        progress["progress"] != "end"
        or int(progress["frame"]) != VIDEO_SECONDS * VIDEO_FPS
        or abs(int(progress["out_time_us"]) - VIDEO_SECONDS * 1_000_000) > 100_000
    ):
        raise ValueError("Video did not decode to the required 90-second recording.")

    with Image.open(directory / "demo.gif") as animation:
        if animation.format != "GIF" or animation.size != VIDEO_SIZE or animation.info["loop"] != 0:
            raise ValueError("Expected a looping 1800-by-1080, 20-second GIF excerpt.")
        frame_count = 0
        for frame in ImageSequence.Iterator(animation):
            frame.load()
            frame_count += 1
            if frame.info["duration"] != 1000 // GIF_FPS:
                raise ValueError("GIF timing differs from the reviewed excerpt.")
        if frame_count != GIF_SECONDS * GIF_FPS:
            raise ValueError("GIF frame count differs from the reviewed excerpt.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check existing media without replacing it."
    )
    args = parser.parse_args()
    result = compute_result(ROOT)
    saved = ROOT / "demo/output/result.json"
    if serialize_result(result, compute_constructed_result()) != saved.read_text(encoding="utf-8"):
        raise ValueError("The live result differs from the reviewed artifact. Review it first.")
    directory = ROOT / "docs"
    if args.check:
        verify_media(result, directory)
        print("PNGs and recordings checked. Playback review is still required.")
    else:
        for name, is_severed in (("before", False), ("after", True)):
            render_graph(result, is_severed).save(directory / f"fortune600-{name}.png")
        print("Graph PNGs rendered. The video and GIF were not changed.")


if __name__ == "__main__":
    main()
