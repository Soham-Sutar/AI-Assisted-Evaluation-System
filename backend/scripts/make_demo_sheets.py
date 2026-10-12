"""Render synthetic handwriting-like answer sheets (NOT real handwriting) for demo uploads.
Student answers differ in quality (full / partial / wrong / blank) so human-vs-AI discrepancies can occur naturally."""
from pathlib import Path

from app.utils.sheetgen import render_page

OUT = Path("demo_sheets")
GOOD = {
    1: "Process scheduling is how the operating system decides which process gets the CPU next. Algorithms include first come first served, shortest job first, round robin and priority scheduling. The aim is high CPU utilisation and throughput with low waiting time.",
    2: "Deadlock prevention breaks at least one of the four necessary conditions: mutual exclusion, hold and wait, no preemption and circular wait. For example a process can request all resources at once, and resources can be given a global ordering.",
    3: "Paging uses fixed size pages and frames so there is no external fragmentation but some internal fragmentation. Segmentation uses variable sized logical segments like code, stack and data, which fits the programmer's view but can cause external fragmentation.",
}
PARTIAL = {
    1: "Process scheduling is when the operating system decides which process will run on the CPU. An example is round robin.",
    2: "Deadlock happens when processes wait forever. To prevent it we avoid circular wait by ordering the resources.",
    3: "Paging divides memory into pages. Segmentation divides memory into segments.",
}
WEAK = {
    1: "The scheduler is a part of the computer that is important for many things.",
    2: "Deadlock is when the computer hangs and you restart it.",
    3: "Paging and segmentation are both techniques used in computers and they are quite different from each other in many ways.",
}
PLAN = {"2022IS001": ("Q{n}", GOOD, 0.0), "2022IS002": ("Question {n}:", PARTIAL, 1.1),
        "2022IS003": ("{n}.", WEAK, -0.9), "2022IS004": ("Q{n}", GOOD, -0.6), "2022IS005": ("{n})", PARTIAL, 0.5),
        "2022IS006": ("Q{n}", WEAK, 0.8)}


def make():
    OUT.mkdir(exist_ok=True)
    for i, (reg, (fmt, answers, skew)) in enumerate(PLAN.items()):
        items = [("header", f"Operating Systems - Internal Assessment 1 - {reg}")]
        for n in (1, 2, 3):
            items += [("marker", n), ("text", answers[n]), ("gap", 55)]
        render_page(items, marker_fmt=fmt, skew=skew, seed=i + 11).save(OUT / f"{reg}.png")
    print(f"Wrote {len(PLAN)} synthetic sheets to {OUT.resolve()}")
