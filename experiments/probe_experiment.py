"""Measure separate-chaining lookup costs at different hash-table load factors."""

import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.hash_table import HashTable


BUCKET_COUNT = 4093
MAX_LOAD_FACTOR = 4.0
LOAD_FACTOR_STEP = 0.25
FAILED_PROBES = 10_000
RANDOM_SEED = 2026
RESULTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Measurement:
    target_alpha: float
    actual_alpha: float
    item_count: int
    successful_average: float
    successful_theory: float
    unsuccessful_average: float
    unsuccessful_theory: float


def _make_urls(count: int, generator: random.Random) -> tuple[list[str], list[str]]:
    stored_urls = [
        f"https://random.example/{generator.getrandbits(128):032x}/{index}"
        for index in range(count)
    ]
    missing_urls = [
        f"https://missing.example/{generator.getrandbits(128):032x}/{index}"
        for index in range(FAILED_PROBES)
    ]
    return stored_urls, missing_urls


def _average_comparisons(table: HashTable[str], urls: list[str], missing: bool) -> float:
    comparisons = 0
    for url in urls:
        if missing:
            try:
                table.get(url)
            except KeyError:
                pass
            else:
                raise RuntimeError(f"Expected URL to be absent: {url}")
        else:
            table.get(url)
        comparisons += table.last_comparisons
    return comparisons / len(urls)


def _measurements() -> list[Measurement]:
    generator = random.Random(RANDOM_SEED)
    maximum_items = round(MAX_LOAD_FACTOR * BUCKET_COUNT)
    stored_urls, missing_urls = _make_urls(maximum_items, generator)
    table: HashTable[str] = HashTable(
        bucket_count=BUCKET_COUNT,
        max_load=None,
    )
    results = []
    previous_count = 0

    step_count = round(MAX_LOAD_FACTOR / LOAD_FACTOR_STEP)
    for step in range(1, step_count + 1):
        target_alpha = step * LOAD_FACTOR_STEP
        item_count = round(target_alpha * BUCKET_COUNT)
        for url in stored_urls[previous_count:item_count]:
            table.set(url, url)
        previous_count = item_count

        actual_alpha = len(table) / BUCKET_COUNT
        successful_average = _average_comparisons(
            table,
            stored_urls[:item_count],
            missing=False,
        )
        unsuccessful_average = _average_comparisons(
            table,
            missing_urls,
            missing=True,
        )
        results.append(
            Measurement(
                target_alpha=target_alpha,
                actual_alpha=actual_alpha,
                item_count=item_count,
                successful_average=successful_average,
                successful_theory=1 + actual_alpha / 2,
                unsuccessful_average=unsuccessful_average,
                unsuccessful_theory=actual_alpha,
            )
        )

    return results


def _write_csv(results: list[Measurement]) -> Path:
    path = RESULTS_DIR / "results.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "items",
                "successful_observed",
                "successful_theory",
                "unsuccessful_observed",
                "unsuccessful_theory",
            )
        )
        for result in results:
            writer.writerow(
                (
                    f"{result.target_alpha:.2f}",
                    f"{result.actual_alpha:.6f}",
                    result.item_count,
                    f"{result.successful_average:.6f}",
                    f"{result.successful_theory:.6f}",
                    f"{result.unsuccessful_average:.6f}",
                    f"{result.unsuccessful_theory:.6f}",
                )
            )
    return path


def _write_svg(results: list[Measurement]) -> Path:
    path = RESULTS_DIR / "results.svg"
    width, height = 900, 600
    left, right, top, bottom = 82, 30, 45, 105
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_alpha, max_comparisons = MAX_LOAD_FACTOR, 5.0

    def x_position(alpha: float) -> float:
        return left + alpha / max_alpha * plot_width

    def y_position(comparisons: float) -> float:
        return top + (max_comparisons - comparisons) / max_comparisons * plot_height

    series = (
        ("Successful: measured", "#1769aa", "successful_average"),
        ("Successful: theory (1 + alpha / 2)", "#1769aa", "successful_theory"),
        ("Unsuccessful: measured", "#c43b3b", "unsuccessful_average"),
        ("Unsuccessful: theory (alpha)", "#c43b3b", "unsuccessful_theory"),
    )
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<title>Average hash-table lookup comparisons by load factor</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="25" text-anchor="middle" font-family="sans-serif" '
        'font-size="18">Average lookup comparisons vs. load factor</text>',
    ]

    for tick in range(6):
        y = y_position(float(tick))
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
            'stroke="#dddddd"/>'
        )
        elements.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="12">{tick}</text>'
        )

    for tick in range(9):
        alpha = tick * 0.5
        x = x_position(alpha)
        elements.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height - bottom}" '
            'stroke="#eeeeee"/>'
        )
        elements.append(
            f'<text x="{x:.2f}" y="{height - bottom + 22}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="12">{alpha:.1f}</text>'
        )

    elements.extend(
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" '
            'stroke="#333333"/>',
            f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" '
            f'y2="{height - bottom}" stroke="#333333"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height - 20}" '
            'text-anchor="middle" font-family="sans-serif" font-size="14">'
            "Load factor (alpha)</text>",
            f'<text x="20" y="{top + plot_height / 2:.2f}" '
            f'transform="rotate(-90 20 {top + plot_height / 2:.2f})" '
            'text-anchor="middle" font-family="sans-serif" font-size="14">'
            "Average compared nodes</text>",
        )
    )

    for label, color, attribute in series:
        points = " ".join(
            f"{x_position(result.actual_alpha):.2f},"
            f"{y_position(getattr(result, attribute)):.2f}"
            for result in results
        )
        dash = ' stroke-dasharray="6 4"' if attribute.endswith("_theory") else ""
        elements.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2"{dash}/>'
        )
        for result in results:
            x = x_position(result.actual_alpha)
            y = y_position(getattr(result, attribute))
            elements.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="{color}"/>'
            )

    legend_left = left + 26
    legend_top = top + 31
    elements.append(
        f'<rect x="{legend_left - 12}" y="{legend_top - 20}" width="342" '
        'height="100" rx="4" fill="white" fill-opacity="0.92" stroke="#cccccc"/>'
    )
    for index, (label, color, attribute) in enumerate(series):
        x = legend_left
        y = legend_top + index * 24
        dash = ' stroke-dasharray="6 4"' if attribute.endswith("_theory") else ""
        elements.append(
            f'<line x1="{x}" y1="{y}" x2="{x + 24}" y2="{y}" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
        elements.append(
            f'<text x="{x + 30}" y="{y + 4}" font-family="sans-serif" '
            f'font-size="11">{label}</text>'
        )

    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")
    return path


def main() -> None:
    results = _measurements()
    csv_path = _write_csv(results)
    svg_path = _write_svg(results)

    print(
        "target alpha | actual alpha | successful (measured / theory) "
        "| unsuccessful (measured / theory)"
    )
    for result in results:
        print(
            f"{result.target_alpha:11.2f} | {result.actual_alpha:12.6f} | "
            f"{result.successful_average:8.4f} / {result.successful_theory:6.4f} | "
            f"{result.unsuccessful_average:10.4f} / "
            f"{result.unsuccessful_theory:6.4f}"
        )
    print(f"\nWrote {csv_path.relative_to(ROOT)} and {svg_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
