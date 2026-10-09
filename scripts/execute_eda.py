"""Execute the EDA notebook offline from both supported working directories."""

import hashlib
import os
from pathlib import Path
import sys

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "01_eda.ipynb"


def data_snapshot():
    return {
        path.relative_to(ROOT / "data").as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in (ROOT / "data").rglob("*") if path.is_file()
    }


def main():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Use the project's .venv interpreter to run this script.")
    before = data_snapshot()
    template = nbformat.read(NOTEBOOK, as_version=4)
    first_result = None
    # The kernel uses this exact interpreter; no global kernelspec installation.
    for label, cwd in [("repository root", ROOT), ("notebooks directory", ROOT / "notebooks")]:
        notebook = nbformat.from_dict(template)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.outputs = []
                cell.execution_count = None
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [
            sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"
        ]
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        try:
            NotebookClient(
                notebook, km=manager, timeout=180, allow_errors=False,
                resources={"metadata": {"path": str(cwd)}},
            ).execute(env=environment)
        finally:
            # Supplying a manager makes the caller responsible for cleanup.
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)
            manager.cleanup_resources()
            if before != data_snapshot():
                raise RuntimeError("Existing data files changed during notebook execution.")
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        assert all(cell.execution_count is not None for cell in code_cells)
        outputs = [output for cell in code_cells for output in cell.outputs]
        assert not any(output.output_type == "error" for output in outputs)
        images = [output for output in outputs if "image/png" in output.get("data", {})]
        assert len(images) == 7, f"Expected seven rendered figures; found {len(images)}"
        nbformat.validate(notebook)
        print(f"PASS: {label}: {len(code_cells)} code cells, {len(images)} rendered figures.")
        if first_result is None:
            first_result = nbformat.from_dict(notebook)
    nbformat.write(first_result, NOTEBOOK)
    print(f"PASS: all {len(before)} existing data files unchanged (hash, size, modification time).")
    print("Saved executed notebook: notebooks/01_eda.ipynb")


if __name__ == "__main__":
    main()
