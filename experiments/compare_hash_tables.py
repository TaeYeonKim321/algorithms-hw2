"""Compare separate chaining and linear probing across load factors."""

import csv
import html
import random
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.hash_table import HashTable
from src.linear_probing_hash_table import LinearProbingHashTable


BUCKET_COUNT = 4093
LOAD_FACTORS = tuple(step / 10 for step in range(1, 10))
SEEDS = (2026, 4817, 7301, 9919, 12_347)
REPEAT_COUNT = len(SEEDS)
RESULTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Measurement:
    target_alpha: float
    actual_alpha: float
    item_count: int
    repeat_count: int
    chaining_success_average: float
    chaining_success_theory: float
    chaining_unsuccessful_average: float
    chaining_unsuccessful_theory: float
    linear_success_average: float
    linear_success_theory: float
    linear_unsuccessful_average: float
    linear_unsuccessful_theory: float


def _make_urls(count: int, generator: random.Random) -> tuple[list[str], list[str]]:
    stored_urls = [
        f"https://stored.example/{generator.getrandbits(128):032x}/{index}"
        for index in range(count)
    ]
    missing_urls = [
        f"https://missing.example/{generator.getrandbits(128):032x}/{index}"
        for index in range(count)
    ]
    return stored_urls, missing_urls


def _average_cost(table, urls: list[str], missing: bool, cost_attribute: str) -> float:
    total_cost = 0
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
        total_cost += getattr(table, cost_attribute)
    return total_cost / len(urls)


def _measurements() -> list[Measurement]:
    results = []
    for target_alpha in LOAD_FACTORS:
        item_count = round(target_alpha * BUCKET_COUNT)
        actual_alpha = item_count / BUCKET_COUNT
        chaining_success_costs = []
        chaining_failure_costs = []
        linear_success_costs = []
        linear_failure_costs = []

        for seed in SEEDS:
            stored_urls, missing_urls = _make_urls(
                item_count,
                random.Random(seed),
            )
            chaining_table: HashTable[str] = HashTable(
                bucket_count=BUCKET_COUNT,
                max_load=None,
            )
            linear_table: LinearProbingHashTable[str] = LinearProbingHashTable(
                bucket_count=BUCKET_COUNT,
                max_load=None,
            )
            for url in stored_urls:
                chaining_table.set(url, url)
                linear_table.set(url, url)

            if len(chaining_table) != item_count or len(linear_table) != item_count:
                raise RuntimeError("A hash table did not store the expected URL count")

            chaining_success_costs.append(
                _average_cost(
                    chaining_table,
                    stored_urls,
                    missing=False,
                    cost_attribute="last_comparisons",
                )
            )
            chaining_failure_costs.append(
                _average_cost(
                    chaining_table,
                    missing_urls,
                    missing=True,
                    cost_attribute="last_comparisons",
                )
            )
            linear_success_costs.append(
                _average_cost(
                    linear_table,
                    stored_urls,
                    missing=False,
                    cost_attribute="last_probes",
                )
            )
            linear_failure_costs.append(
                _average_cost(
                    linear_table,
                    missing_urls,
                    missing=True,
                    cost_attribute="last_probes",
                )
            )

        results.append(
            Measurement(
                target_alpha=target_alpha,
                actual_alpha=actual_alpha,
                item_count=item_count,
                repeat_count=REPEAT_COUNT,
                chaining_success_average=sum(chaining_success_costs) / REPEAT_COUNT,
                chaining_success_theory=1 + actual_alpha / 2,
                chaining_unsuccessful_average=sum(chaining_failure_costs)
                / REPEAT_COUNT,
                chaining_unsuccessful_theory=actual_alpha,
                linear_success_average=sum(linear_success_costs) / REPEAT_COUNT,
                linear_success_theory=0.5
                * (1 + 1 / (1 - actual_alpha)),
                linear_unsuccessful_average=sum(linear_failure_costs)
                / REPEAT_COUNT,
                linear_unsuccessful_theory=0.5
                * (1 + 1 / (1 - actual_alpha) ** 2),
            )
        )
    return results


def _write_csv(results: list[Measurement]) -> Path:
    path = RESULTS_DIR / "compare_results.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = (
        "target_alpha",
        "actual_alpha",
        "items",
        "repeats",
        "chaining_success_observed",
        "chaining_success_theory",
        "chaining_unsuccessful_observed",
        "chaining_unsuccessful_theory",
        "linear_success_observed",
        "linear_success_theory",
        "linear_unsuccessful_observed",
        "linear_unsuccessful_theory",
    )
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(headers)
        for result in results:
            writer.writerow(
                (
                    f"{result.target_alpha:.2f}",
                    f"{result.actual_alpha:.6f}",
                    result.item_count,
                    result.repeat_count,
                    f"{result.chaining_success_average:.9f}",
                    f"{result.chaining_success_theory:.9f}",
                    f"{result.chaining_unsuccessful_average:.9f}",
                    f"{result.chaining_unsuccessful_theory:.9f}",
                    f"{result.linear_success_average:.9f}",
                    f"{result.linear_success_theory:.9f}",
                    f"{result.linear_unsuccessful_average:.9f}",
                    f"{result.linear_unsuccessful_theory:.9f}",
                )
            )
    return path


def _write_svg(results: list[Measurement]) -> Path:
    path = RESULTS_DIR / "compare_results.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1000, 620
    left, right, top, bottom = 82, 32, 48, 125
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [
        getattr(result, field)
        for result in results
        for field in (
            "chaining_success_average",
            "chaining_success_theory",
            "chaining_unsuccessful_average",
            "chaining_unsuccessful_theory",
            "linear_success_average",
            "linear_success_theory",
            "linear_unsuccessful_average",
            "linear_unsuccessful_theory",
        )
    ]
    max_cost = max(values) * 1.1

    def x_position(alpha: float) -> float:
        return left + alpha * plot_width

    def y_position(cost: float) -> float:
        return top + (max_cost - cost) / max_cost * plot_height

    series = (
        ("Chaining success: measured", "#1769aa", "chaining_success_average"),
        ("Chaining success: theory", "#1769aa", "chaining_success_theory"),
        (
            "Chaining unsuccessful: measured",
            "#c43b3b",
            "chaining_unsuccessful_average",
        ),
        (
            "Chaining unsuccessful: theory",
            "#c43b3b",
            "chaining_unsuccessful_theory",
        ),
        ("Linear success: measured", "#218739", "linear_success_average"),
        ("Linear success: theory", "#218739", "linear_success_theory"),
        (
            "Linear unsuccessful: measured",
            "#8a45a5",
            "linear_unsuccessful_average",
        ),
        (
            "Linear unsuccessful: theory",
            "#8a45a5",
            "linear_unsuccessful_theory",
        ),
    )
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<title>Hash table lookup costs by load factor</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="27" text-anchor="middle" font-family="sans-serif" '
        'font-size="18">Average lookup cost by load factor</text>',
    ]

    for tick in range(6):
        cost = max_cost * tick / 5
        y = y_position(cost)
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
            'stroke="#dddddd"/>'
        )
        elements.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="12">{cost:.1f}</text>'
        )

    for tick in range(0, 11):
        alpha = tick / 10
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
            "Average probes / comparisons</text>",
        )
    )

    for label, color, attribute in series:
        points = " ".join(
            f"{x_position(result.actual_alpha):.2f},"
            f"{y_position(getattr(result, attribute)):.2f}"
            for result in results
        )
        is_theory = attribute.endswith("_theory")
        dash = ' stroke-dasharray="6 4"' if is_theory else ""
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

    legend_left, legend_top = left + 28, top + 24
    legend_width, legend_height = 390, 8 * 21 + 18
    elements.append(
        f'<rect x="{legend_left - 12}" y="{legend_top - 18}" '
        f'width="{legend_width}" height="{legend_height}" rx="4" fill="white" '
        'fill-opacity="0.94" stroke="#cccccc"/>'
    )
    for index, (label, color, attribute) in enumerate(series):
        x = legend_left
        y = legend_top + index * 21
        dash = (
            ' stroke-dasharray="6 4"'
            if attribute.endswith("_theory")
            else ""
        )
        elements.append(
            f'<line x1="{x}" y1="{y}" x2="{x + 24}" y2="{y}" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
        elements.append(
            f'<text x="{x + 30}" y="{y + 4}" font-family="sans-serif" '
            f'font-size="11">{html.escape(label)}</text>'
        )

    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")
    return path


def main() -> None:
    results = _measurements()
    csv_path = _write_csv(results)
    svg_path = _write_svg(results)

    print(
        "target alpha | actual alpha | chaining (success / miss) "
        "| linear (success / miss)"
    )
    for result in results:
        print(
            f"{result.target_alpha:11.2f} | {result.actual_alpha:12.6f} | "
            f"{result.chaining_success_average:7.3f} / "
            f"{result.chaining_unsuccessful_average:7.3f} | "
            f"{result.linear_success_average:7.3f} / "
            f"{result.linear_unsuccessful_average:7.3f}"
        )
    print(f"\nWrote {csv_path.relative_to(ROOT)} and {svg_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
