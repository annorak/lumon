"""Render the Fortune 600 PNG and check the reviewed terminal recordings."""

import argparse
import subprocess
import textwrap
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg  # type: ignore[import-untyped]
from demo.run_demo import DemoResult, compute_result, serialize_result
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1600, 1200)
INK = "#182830"
PAPER = "#F6F4EE"
TEAL = "#007D71"
RUST = "#B24F35"
VIDEO_SIZE = (1800, 1080)
VIDEO_SECONDS = 90
VIDEO_FPS = 24
GIF_START_SECONDS = 13.5
GIF_SECONDS = 20
GIF_FPS = 10


def draw_text(
    image: Image.Image,
    position: tuple[int, int],
    text: str,
    *,
    size: int = 24,
    columns: int = 100,
    color: str = INK,
) -> None:
    wrapped = "\n".join(
        "\n".join(textwrap.wrap(line, columns, break_long_words=False, break_on_hyphens=False))
        for line in text.split("\n")
    )
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=size)
    bounds = draw.multiline_textbbox(position, wrapped, font=font, spacing=8)
    if bounds[2] > SIZE[0] - 24 or bounds[3] > SIZE[1] - 24:
        raise ValueError(f"Media text exceeds the canvas: {text[:80]}")
    draw.multiline_text(position, wrapped, font=font, fill=color, spacing=8)


def draw_path(
    image: Image.Image,
    result: DemoResult,
    x: int,
    removed_ids: set[str],
    remaining_color: str,
) -> None:
    (path,) = result.paths.paths
    nodes = {node.id: node for node in result.graph.nodes}
    edges = {edge.id: edge for edge in result.graph.edges}
    labels = {
        "reaches": "Reach endpoint",
        "exploits": "Exploit",
        "reads": "Read credentials",
        "authenticates_as": "Authenticate to cloud",
    }
    draw = ImageDraw.Draw(image)
    for index, node_id in enumerate(path.node_ids):
        top = 448 + index * 100
        bottom = top + 56
        draw.rounded_rectangle((x, top, x + 696, bottom), radius=10, fill="white")
        draw_text(image, (x + 18, top + 14), nodes[node_id].label, size=24, columns=55)
        if index == len(path.edge_ids):
            continue

        edge = edges[path.edge_ids[index]]
        is_removed = edge.id in removed_ids
        color = RUST if is_removed else remaining_color
        edge_x = x + 24
        next_top = top + 100
        midpoint = (bottom + next_top) // 2
        if is_removed:
            draw.line((edge_x, bottom, edge_x, midpoint - 12), fill=color, width=4)
            draw.line((edge_x, midpoint + 12, edge_x, next_top), fill=color, width=4)
            draw.line((edge_x - 7, midpoint - 7, edge_x + 7, midpoint + 7), fill=color, width=4)
            draw.line((edge_x - 7, midpoint + 7, edge_x + 7, midpoint - 7), fill=color, width=4)
        else:
            draw.line((edge_x, bottom, edge_x, next_top - 2), fill=color, width=4)
            draw.polygon(
                ((edge_x - 7, next_top - 10), (edge_x + 7, next_top - 10), (edge_x, next_top - 2)),
                fill=color,
            )
        label = labels[edge.type.value]
        if edge.enabled_by:
            label += f": {nodes[edge.enabled_by].label} [{edge.enabled_by}]"
        if is_removed:
            label += " / REMOVED"
        draw_text(image, (x + 56, bottom + 10), label, size=20, columns=68, color=color)


def render_poster(result: DemoResult) -> Image.Image:
    # Both panels use the same source-backed route and computed removal set.
    (path,) = result.paths.paths
    (selected,) = result.ranked_interventions
    image = Image.new("RGB", SIZE, PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, SIZE[0], 12), fill=TEAL)
    draw_text(image, (48, 36), "Fortune 600: the kill chain and Lumon's fix", size=36)
    draw_text(image, (48, 92), result.headline, size=22, columns=115)

    draw.rectangle((48, 216, 1552, 324), fill="white", outline="#D1D6D3", width=2)
    draw.line((48, 254, 1552, 254), fill="#D1D6D3", width=2)
    for x in (132, 998, 1324):
        draw.line((x, 216, x, 324), fill="#D1D6D3", width=2)
    for x, label in (
        (64, "Rank"),
        (150, "Selected intervention"),
        (1020, "Cost / provenance"),
        (1350, "Paths severed"),
    ):
        draw_text(image, (x, 228), label, size=20)
    draw_text(image, (64, 272), str(selected.rank))
    draw_text(
        image,
        (150, 272),
        f"{selected.intervention.id}: {selected.intervention.name}",
        size=24,
    )
    draw_text(image, (1020, 264), f"{selected.cost_units:g} assumed implementation unit", size=18)
    draw_text(
        image,
        (1020, 294),
        selected.intervention.cost.source.value.replace("_", " "),
        size=18,
    )
    draw_text(image, (1350, 272), ", ".join(selected.covered_path_ids), size=22)

    draw_text(
        image,
        (48, 338),
        "Display order: cost ascending, individual severed weight descending, then ID. "
        "Not implementation priority.",
        size=18,
        columns=140,
    )

    draw_text(image, (48, 364), "Before", size=32)
    draw_text(image, (48, 408), f"Source-reported route {path.id}", size=22)
    draw_text(image, (856, 364), f"After {selected.intervention.id}", size=32)
    draw_text(
        image,
        (856, 408),
        f"{len(result.solution.covered_path_ids)}/{len(result.paths.paths)} "
        "supplied validated paths severed",
        size=22,
    )
    draw_path(image, result, 48, set(), TEAL)
    draw_path(image, result, 856, set(result.removed_transition_ids), "#69747A")

    draw_text(
        image,
        (48, 1040),
        "All transitions: source-validated. Gray: retained in the model. Red X: selected removal.",
        size=20,
    )
    draw_text(
        image,
        (48, 1076),
        "Modeled effects on supplied paths only. Other transitions remain. "
        f"Minimum-cost full cover: {result.solution.guarantee.value.upper()}.",
        size=20,
    )
    draw_text(
        image,
        (48, 1112),
        "Customer changes were not reported; numerical comparison is unavailable.",
        size=20,
    )
    draw_text(image, (48, 1150), result.repository_url, size=18)
    return image


def verify_media(expected_poster: Image.Image, directory: Path) -> None:
    with Image.open(directory / "demo.png") as poster:
        if poster.format != "PNG" or poster.size != SIZE:
            raise ValueError("Expected a full-size PNG release image.")
        if ImageChops.difference(poster.convert("RGB"), expected_poster).getbbox():
            raise ValueError("PNG differs from the current computed result.")

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

    excerpt = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-ss",
            str(GIF_START_SECONDS),
            "-t",
            str(GIF_SECONDS),
            "-i",
            str(directory / "demo.mp4"),
            "-filter_complex",
            f"[0:v]fps={GIF_FPS},split[frames][colors];"
            "[colors]palettegen=stats_mode=diff[palette];"
            "[frames][palette]paletteuse=dither=none",
            "-loop",
            "0",
            "-f",
            "gif",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
        timeout=120,
    )
    with (
        Image.open(directory / "demo.gif") as animation,
        Image.open(BytesIO(excerpt.stdout)) as reference,
    ):
        if (
            animation.format != "GIF"
            or animation.size != VIDEO_SIZE
            or reference.size != VIDEO_SIZE
            or animation.info["loop"] != 0
        ):
            raise ValueError("Expected a looping 1800-by-1080, 20-second GIF excerpt.")
        frame_count = 0
        for frame, expected in zip(
            ImageSequence.Iterator(animation), ImageSequence.Iterator(reference), strict=True
        ):
            frame_count += 1
            if frame.info["duration"] != 1000 // GIF_FPS:
                raise ValueError("GIF timing differs from the reviewed excerpt.")
            if ImageChops.difference(frame.convert("RGB"), expected.convert("RGB")).getbbox():
                raise ValueError("GIF differs from the corresponding video excerpt.")
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
    if serialize_result(result) != saved.read_text(encoding="utf-8"):
        raise ValueError("The live result differs from the reviewed artifact. Review it first.")
    poster = render_poster(result)
    directory = ROOT / "docs"
    if args.check:
        verify_media(poster, directory)
        print("PNG and recordings checked. Playback review is still required.")
    else:
        poster.save(directory / "demo.png")
        print("PNG rendered. The video and GIF were not changed.")


if __name__ == "__main__":
    main()
