import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
bench_files = {
    "bench_app/main/CMakeLists.txt", "bench_app/main/bench_main.c",
    "bench_app/main/bench_extended_mean.c", "bench_app/main/bench_extended_pool.c",
}
harness = (
    "bench_app/components/bench_harness/bench.c",
    "bench_app/components/bench_harness/include/bench.h",
)
versions = {
    "stock": "ace42ac7721119cd543fc40ffe719e601fa8f20f",
    "exp_mean": "4bfa49c64a932f700688c2007a01d8ea1fa102ac",
    "opt2": "edb003c6770491abb74766835f4c803b9d4f5a20",
}
reference = None
for build, revision in versions.items():
    repo = root / build / "esp-nn"
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])
    assert git("rev-parse", "HEAD").decode().strip() == revision
    assert git("rev-parse", "--abbrev-ref", "HEAD").strip() == b"HEAD"
    modified = {s[3:] for s in git("status", "--porcelain").decode().splitlines()}
    assert modified == bench_files, modified
    for rel in harness:
        content = (repo / rel).read_bytes()
        assert content == git("show", f"HEAD:{rel}")
        print(f"{build} {rel} sha256={hashlib.sha256(content).hexdigest()}")
    app = repo / "bench_app"
    cfg = (app / "sdkconfig").read_bytes()
    (root / "results" / f"{build}.sdkconfig").write_bytes(cfg)
    print(f"{build} sdkconfig sha256={hashlib.sha256(cfg).hexdigest()}")
    elf = app / "build/bench_app.elf"
    binary = app / "build/bench_app.bin"
    for file in (elf, binary):
        print(f"{build} {file.name} sha256={hashlib.sha256(file.read_bytes()).hexdigest()}")
    db = json.loads((app / "build/compile_commands.json").read_text())
    def normalize(value):
        return value.replace(str(repo), "<WORKTREE>")
    commands = {normalize(item["file"]): normalize(item["command"]) for item in db}
    if reference is None:
        reference = commands
        stock_cfg = cfg
    else:
        assert stock_cfg == cfg
        assert all(reference[name] == commands[name] for name in reference)
        extra = commands.keys() - reference.keys()
        expected = {"<WORKTREE>/src/common/esp_nn_mean_qacc_s8_esp32s3.S"} if build == "exp_mean" else set()
        assert extra == expected, extra
        print(f"{build} all {len(reference)} shared compile commands match stock; added={sorted(extra)}")
print("PASS: exact commits; detached heads; isolated app changes; unmodified vendor harness; identical SDK configuration")
