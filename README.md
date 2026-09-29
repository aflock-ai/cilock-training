# cilock training: build receipts

A 10-minute, hands-on lesson. A tiny desktop app goes through build, test and package. Every step leaves a signed
receipt. Before release, one check compares the receipts with a short rulebook and answers **PASS** or **BLOCKED**,
with the reason.

No supply-chain background needed. Runs on your laptop. The only network use is cilock fetching a signed
timestamp from a public timestamp server (TSA); nothing is uploaded.

## Watch first (5.5 min, subtitled)

- [Explainer video, subtitled](media/cilock-build-receipts-explainer.mp4)
- [Explainer video, narrated and subtitled](media/cilock-build-receipts-explainer-narrated.mp4)
- [Slides (PDF)](media/cilock-build-receipts-slides.pdf) · [one-page summary (PDF)](media/cilock-build-receipts-onepager.pdf) · [slides (HTML, download and open in a browser)](media/cilock-build-receipts-slides.html)

It covers both lessons: receipts and the one check before release, the three ways a release gets blocked, where the
two commands go in CI, and iterating the policy until it is right.

Commands, verdicts and timings on screen come from a real run of this lesson on Linux; the policy iteration table
comes from the policy test harness.

## The idea in plain words

Today a release team usually signs and ships the file it is handed. It cannot see what happened before that:

- Was the app built from the right code?
- Did the tests really run, and pass?
- Is the file in the package the same file the build produced?

**Receipts answer those questions.** Each build step runs under `cilock run`, which writes a receipt: what command
ran, which files went in, which files came out, whether it succeeded, and which commit it came from. The build
machine signs the receipt, so any later edit is detected.

**The rulebook says what a good release looks like.** In this lesson it has three rules:

1. The build ran and finished cleanly.
2. The tests ran against that build and passed.
3. The package holds the exact binary the build produced.

The release team signs the rulebook, so it cannot be changed quietly.

**One check before release.** `cilock verify` reads the package, the receipts and the signed rulebook:

```
  ✅ PASS: every rule met. OK to sign and release.
```

or

```
  ⛔ BLOCKED: do not release.
    The photo-lite in the package is not the one the build produced.
    (cilock: mismatched digests for photo-lite)
```

The lesson runs four cases:

| Case | Result | Why |
|---|---|---|
| Normal release | ✅ PASS | All three rules hold |
| Binary swapped after the tests, then packaged | ⛔ BLOCKED | Rule 3: the packaged binary is not the built one |
| Tests skipped | ⛔ BLOCKED | Rule 2: no receipt for the `test` step |
| Tests failed, release went ahead | ⛔ BLOCKED | Rule 2: the test receipt records exit code 3 |

## Quickstart

You need `git`, `openssl`, `tar`, `python3`, a C compiler (`cc`, `gcc` or `clang`; set `CC=` to pick one), and
cilock.

### Install cilock

The lesson uses a flag that is newer than the current packaged release (`--material-manifest` on `cilock run`). Until a release includes them, build cilock from source at the
commit this lesson is tested against (needs Go 1.26):

```bash
scripts/install-cilock.sh          # builds ./bin/cilock from aflock-ai/rookery at a pinned commit
export PATH="$PWD/bin:$PATH"
```

Once a newer release is out, `brew install aflock-ai/tap/cilock` or a download from
[aflock-ai/cilock](https://github.com/aflock-ai/cilock) will work the same way. Check with
`cilock run --help | grep material-manifest`.

### Run the lesson

```bash
./demo.sh                  # paced for reading
DEMO_FAST=1 ./demo.sh      # no pauses
```

Everything the lesson creates goes in `./lesson-work/` (keys, receipts, policy, logs). The script exits 0 only if
all four cases end as described above.

**Windows:** run it from Git Bash with a C compiler on `PATH` (for example MinGW `gcc`). CI runs it on
`windows-latest`; see the [workflow](.github/workflows/lesson.yml) for the current result.

## How it works

The script prints every cilock command in full before it runs it. These are the ones that matter.

**1. Keys.** Two ed25519 keys: one for the build machine (signs receipts), one for the release team (signs the
rulebook). In production the build machine would use short-lived certificates from your signing service instead
of a key file.

**2. The rulebook** is a cilock policy built from the three files in `rules/` by `tools/make_policy.py`. Each step
lists who may sign its receipt and a Rego rule its `command-run` attestation must pass. `test` and `package` also
declare `artifactsFrom: ["build"]`, which is what enforces rule 3.

```bash
python3 tools/make_policy.py keys/build-machine.pub policy/policy.json
cilock policy validate -p policy/policy.json
cilock sign -k keys/release-team.key -f policy/policy.json -o policy/policy.signed.json
```

**3. Receipts.** Each existing command is prefixed with `cilock run --step <name> ... --`:

```bash
cilock run --step build   -k keys/build-machine.key -a git --material-manifest \
    -o evidence/build.json   -- cc app/photo_lite.c -o photo-lite
cilock run --step test    -k keys/build-machine.key -a git --material-manifest \
    -o evidence/test.json    -- ./photo-lite
cilock run --step package -k keys/build-machine.key -a git --material-manifest \
    -o evidence/package.json -- tar czf photo-lite.tar.gz photo-lite
```

`tools/show_receipt.py evidence/build.json` prints one in plain English.

**4. The check:**

```bash
cilock verify photo-lite.tar.gz \
    -p policy/policy.signed.json -k keys/release-team.pub \
    -s "sha1:$(git rev-parse HEAD)" \
    -a evidence/build.json -a evidence/test.json -a evidence/package.json
```

Exit code 0 is PASS. Anything else is BLOCKED, and the log says which step and rule failed. Branch on the exit
code, not on grepped output.

In `demo.sh`, `demo_step` and `demo_verify` are script helpers that print and run exactly these commands with the
lesson's paths. They are not cilock commands.

## Lesson 2: iterate a policy against known-good and known-bad builds (the loop an AI agent runs)

Lesson 1 hands you a finished policy. Lesson 2 shows how you get there: write a first draft, test it against builds
whose right answer you already know, fix what the tests show, repeat. The loop is mechanical, so an AI agent can run
it, as long as a person decides what the fixtures are and what counts as done.

```bash
./lesson2.sh
```

It builds four fixtures once, each a real set of signed receipts:

| Fixture | What happened | Right answer |
|---|---|---|
| `good` | build, test, package | PASS |
| `swapped` | binary replaced before packaging | BLOCKED |
| `skipped` | no test step | BLOCKED |
| `failed` | test step exits 3 | BLOCKED |

Then three rounds. Each round builds the policy, runs `cilock policy validate`, signs it, and runs `cilock verify`
against every fixture:

| Round | Change | Validate findings | Verdicts correct |
|---|---|---|---|
| 1 | First draft (`rules-v1/`, no `artifactsFrom`) | 6 | 3/4: the swapped binary passes |
| 2 | Add `artifactsFrom` so test and package must use the build's output | 6 | 4/4 |
| 3 | Fix the Rego guard the validator flagged (`rules/`) | 0 | 4/4 |

**Stop condition: zero validate findings and all four verdicts correct.** Round 2 already gets every verdict right,
but the validator still reports that `not is_number(input.exitcode)` inside `deny` can never fire when the field is
missing, so a receipt without an exit code would pass. The fixtures do not cover that case; the validator does.
That is why the stop condition needs both.

`cilock policy validate` prints `Policy validation: PASSED` even when it lists findings, and exits 0. Count the
numbered findings; do not trust the exit code. The script does this.

Each round is recorded in `lesson2-work/loop.jsonl`: the policy, the validate output, each verdict and the time.
The script exits 0 only if the three rounds end as in the table. It avoids bash associative arrays, so it runs
on the bash 3.2 that macOS ships.

## Gotchas

These cost real time while building the lesson.

- **Keep receipts outside the build workspace.** A step's inputs are every file in its working directory. If
  `build.json` is written inside the project folder, the `test` step sees it as an input that no earlier step
  produced, and `artifactsFrom` rejects it ("material(s) not produced by any artifactsFrom step"). The lesson
  writes receipts to `../evidence/`.
- **`--material-manifest` is required for `artifactsFrom`.** Without it, recent cilock builds omit the per-file
  input list, and verify fails with "required file inventory is unavailable: material details were omitted".
- **Seed verify with the commit.** `-s sha1:<commit>` ties all three receipts to one release. With only the package
  file as the seed, the build and test receipts are not found, because their outputs are not the package.
- **Key ID is the sha256 of the public key as Go re-encodes it**, PEM with LF line endings. That equals the sha256
  of the `.pub` file on Linux and macOS, but not on Windows, where openssl writes CRLF. Hashing the raw file there
  gives "public key in policy has expected key id ... but got ...". `tools/make_policy.py` re-encodes the key first.
- **Guard Rego rules with a helper.** `deny[msg] { not is_number(input.exitcode) ... }` never fires when the field is
  missing. Use a helper rule (`has_exit_code { is_number(input.exitcode) }`) and write `not has_exit_code` in the
  deny. cilock warns about the broken form.
- **`-a git` narrows the default attestors** (`environment,git,platform`) to just the commit record, which keeps the
  receipts small and keeps environment variables out of them.
- **A failed step still writes a receipt.** `cilock run` exits non-zero, but the receipt records the failure, so the
  rulebook can reject it with a clear reason.

## Layout

| Path | What it is |
|---|---|
| `demo.sh` | The lesson |
| `app/photo_lite.c` | The app |
| `rules/*.rego` | One rule per step |
| `lesson2.sh` | Lesson 2: the policy iteration loop |
| `rules-v1/*.rego` | Lesson 2's deliberately weak first draft |
| `tools/make_policy.py` | Builds the policy (rulebook) from the rules (`--rules DIR`, `--no-artifacts-from`) |
| `tools/show_receipt.py` | Prints a receipt in plain English |
| `scripts/install-cilock.sh` | Builds cilock from rookery at the pinned commit |
| `.github/workflows/lesson.yml` | Runs both lessons on Linux, macOS and Windows |
| `media/` | Explainer video (subtitled and narrated), slides, one-page summary |

## License

Apache-2.0
