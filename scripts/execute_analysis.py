"""Execute Phase 4 with the project interpreter from both supported directories."""

import copy
import hashlib
import os
from pathlib import Path
import sys

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/02_data_analysis.ipynb"
FIGURES = ["phase4_01_median_sugar.png", "phase4_02_median_protein.png",
           "phase4_03_top_protein_per_100kcal.png", "phase4_04_nutrition_completeness.png",
           "phase4_05_nutriscore_distribution.png"]


def protected_snapshot():
    paths = [p for p in (ROOT / "data").rglob("*") if p.is_file()]
    paths.append(ROOT / "notebooks/01_eda.ipynb")
    return {p.relative_to(ROOT).as_posix():
            (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in paths}


def main():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Use the project's .venv interpreter.")
    before = protected_snapshot()
    template = nbformat.read(NOTEBOOK, as_version=4)
    first_result = None
    first_hashes = None
    for label, cwd in [("repository root", ROOT), ("notebooks directory", ROOT / "notebooks")]:
        notebook = copy.deepcopy(template)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.outputs = []
                cell.execution_count = None
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        try:
            NotebookClient(notebook, km=manager, timeout=180, allow_errors=False,
                           resources={"metadata": {"path": str(cwd)}}).execute(env=environment)
        finally:
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)
            manager.cleanup_resources()
            if protected_snapshot() != before:
                raise RuntimeError("A protected dataset or EDA notebook changed.")
        code_cells = [c for c in notebook.cells if c.cell_type == "code"]
        assert all(c.execution_count is not None for c in code_cells)
        outputs = [o for c in code_cells for o in c.outputs]
        assert not any(o.output_type == "error" for o in outputs)
        images = [o for o in outputs if "image/png" in o.get("data", {})]
        assert len(images) == 5, f"Expected five embedded charts, found {len(images)}"
        hashes = {name: hashlib.sha256((ROOT / "reports/figures" / name).read_bytes()).hexdigest() for name in FIGURES}
        if first_result is None:
            first_result = notebook
            first_hashes = hashes
        else:
            assert hashes == first_hashes, "Charts differ between supported working directories"
        nbformat.validate(notebook)
        print(f"PASS: {label}: {len(code_cells)} code cells; five rendered and exported charts.")
    with NOTEBOOK.open("w", encoding="utf-8", newline="\n") as stream:
        nbformat.write(first_result, stream)
    print(f"PASS: all {len(before)} protected files unchanged; chart hashes identical across both runs.")
    print("Saved executed notebook: notebooks/02_data_analysis.ipynb")


if __name__ == "__main__":
    main()
